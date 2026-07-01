# Read-only Atlassian Auth Wired — Implementation Plan

## Overview

Wire read-only authentication to Jira Cloud + Confluence Cloud into the CLI, so
that S-01 (fetch a Jira ticket) and S-02 (fetch a Confluence page) have a
credential-safe, verified connection to build on. This is F-01 on the roadmap —
a foundation slice, not a user-visible feature on its own, whose sole job is to
get the auth/credential contract right once.

## Current State Analysis

The CLI is a bare Typer scaffold with a single `version` command
(`src/jira_tools/cli.py`). `pyproject.toml` declares only `pydantic` and
`typer` as runtime dependencies — no Atlassian client library, no HTTP client,
no config/secrets handling exists anywhere in the codebase. No credential
storage, loading, or verification code exists. `acli` is not installed on the
development machine and no existing Atlassian env vars or `.netrc` entries were
found, so "reuse acli's session" (floated as an option in `tech-stack.md`) is
not actually available without a separate install/config step outside this
change's scope.

## Desired End State

Running `uv run jira-tools auth-check` after creating a config file:

- Reads Jira Cloud + Confluence Cloud credentials (site URL, email, API token)
  from `~/.config/jira-tools/config.toml` (XDG-aware).
- Builds a read-only Atlassian client for each product and calls a cheap,
  read-only identity endpoint to confirm the credentials work.
- Prints a clear per-product PASS/FAIL report and exits non-zero if either
  check fails — without ever printing the token or including it in any log
  output.
- If the config file is missing or malformed, fails with an actionable error
  message (what file, what fields) instead of a stack trace.

Verification: `uv run jira-tools auth-check` against a real Atlassian Cloud
account (with a valid `~/.config/jira-tools/config.toml`) reports PASS for
both products; with a config pointing at an invalid token, it reports FAIL for
both without leaking the bad token value; with no config file present, it
prints setup instructions and exits non-zero.

### Key Discoveries:

- `src/jira_tools/cli.py:1-16` — only command is `version`; no auth/client
  code to build on or migrate.
- `pyproject.toml:10-13` — deps are `pydantic` + `typer` only; Atlassian
  client library and test-mocking library both need to be added.
- `atlassian-python-api` is built on the `requests` library (not `httpx`), per
  its own docs and constructor patterns (`Jira(url=..., username=..., password=...,
  cloud=True)` / `Confluence(url=..., username=..., password=..., cloud=True)`
  using the API token as the password for Cloud). This determines the HTTP
  mocking library choice for tests (see Phase 4).
- No `acli`, no Atlassian env vars, no relevant `.netrc` entries exist on this
  machine — confirms the API-token path (chosen during questioning) is the
  only currently-viable auth mechanism, not just the preferred one.
- CLAUDE.md requires `pydantic` models at the ADF/API boundary and
  `mypy --strict` — the config model and any parsed identity-check response
  must be typed pydantic models, not raw dicts.

## What We're NOT Doing

- No OAuth 2.0 (3LO) flow — API token is sufficient for a single-user local
  tool and avoids a callback server / token refresh machinery.
- No `acli` session reuse — not installed on this machine, and its session
  format isn't a stable dependency to build on.
- No Server/Data Center support — Cloud only, per the confirmed deployment
  target.
- No interactive `jira-tools auth login` setup wizard — the user hand-writes
  `config.toml`; setup steps go in the README.
- No token encryption/OS-keyring integration — config file storage was the
  chosen mechanism; file-permission warnings are the extent of hardening here.
- No fetch/search methods (`get_issue`, `get_page`, etc.) — those belong to
  S-01/S-02, which will extend the read-only client wrapper built here.
- No environment-variable credential override — config file is the single,
  exclusive credential source for this change.

## Implementation Approach

Four phases, each independently testable: (1) a typed config loader that
never leaks its own contents into logs, (2) a thin read-only wrapper around
`atlassian-python-api`'s Jira/Confluence clients that structurally cannot
expose write methods, (3) a CLI command that exercises both and reports
results, and (4) tests that mock the HTTP layer so no real credentials are
ever needed to verify the code, plus an explicit test that guards the
no-leakage guardrail rather than trusting convention.

## Critical Implementation Details

**HTTP mocking library**: `atlassian-python-api` uses `requests` under the
hood, not `httpx`. Tests must mock with the `responses` library (which
intercepts `requests`), not `respx` (which mocks `httpx` and would silently
not intercept anything here).

## Phase 1: Config & Credential Loading

### Overview

A typed, read-only config model and loader that reads Jira/Confluence Cloud
credentials from a TOML file on disk, with actionable errors and no
credential leakage into logs or exceptions.

### Changes Required:

#### 1. Config model

**File**: `src/jira_tools/config.py`

**Intent**: Define the shape of the credentials the rest of the app needs —
one Atlassian Cloud site URL, an email, and an API token, shared by both Jira
and Confluence per Cloud's auth model.

**Contract**: A `pydantic.BaseModel` (e.g. `AtlassianConfig`) with fields
`site_url: str`, `email: str`, `api_token: str`. Its `__repr__`/`__str__`
must not expose `api_token` in plaintext (pydantic's `SecretStr` field type is
the natural fit here, so accidental `print(config)` / log calls redact it).

#### 2. Config loader

**File**: `src/jira_tools/config.py`

**Intent**: Locate and parse the config file, raising a clear, actionable
error (not a raw exception) when the file is missing or malformed, and
warning (not failing) when the file's permissions are more open than the
owner-only convention this guardrail relies on.

**Contract**: A loader function reads from
`$XDG_CONFIG_HOME/jira-tools/config.toml`, falling back to
`~/.config/jira-tools/config.toml` when `XDG_CONFIG_HOME` is unset, using the
stdlib `tomllib` (available on Python ≥3.11; project requires ≥3.12, so no new
parsing dependency is needed). Missing file → a typed exception whose message
names the expected path and required fields (`site_url`, `email`,
`api_token`). Malformed TOML or missing fields → a typed exception naming
which field is missing/invalid, without echoing the rest of the file's
contents. If the file's POSIX permissions grant read access beyond the owner,
emit a `typer.echo` warning (to stderr) rather than failing the load.

### Success Criteria:

#### Automated Verification:

- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`
- Unit tests pass: `uv run pytest tests/test_config.py`

#### Manual Verification:

- Creating `~/.config/jira-tools/config.toml` with valid fields loads without
  error.
- Deleting/renaming the config file produces a message naming the expected
  path, not a stack trace.
- `chmod 644` on the config file produces a stderr warning; `chmod 600` does
  not.

---

## Phase 2: Read-only Atlassian Client Wrapper

### Overview

A thin internal wrapper around `atlassian-python-api`'s `Jira` and
`Confluence` classes that structurally exposes only read operations, so
downstream code (this change's `auth-check`, and later S-01/S-02) can never
reach a write method even by accident.

### Changes Required:

#### 1. Add dependency

**File**: `pyproject.toml`

**Intent**: Bring in the Atlassian REST client library chosen during
questioning.

**Contract**: Add `atlassian-python-api` to `[project].dependencies`, next to
`pydantic` and `typer`.

#### 2. Read-only client wrapper

**File**: `src/jira_tools/atlassian_client.py`

**Intent**: Construct authenticated `Jira`/`Confluence` client instances from
an `AtlassianConfig`, and expose only the read operations this change needs
(an identity/"who am I" check for each product), so the module's public
surface is the enforcement mechanism for the read-only guardrail rather than
a documented convention. S-01/S-02 extend this module's public surface with
their own read methods (e.g. fetch-issue, fetch-page) rather than reaching
into the underlying library's full client directly.

**Contract**: Two factory functions/classes, one per product (e.g.
`ReadOnlyJiraClient`, `ReadOnlyConfluenceClient`), each constructed from an
`AtlassianConfig` with `cloud=True` and the email/token as
username/password per `atlassian-python-api`'s Cloud auth convention. Each
wrapper exposes exactly one method for this phase — a current-user/identity
check — that calls the underlying library's read-only "who am I" endpoint for
that product and returns a typed result (e.g. a pydantic model with
`display_name: str`) rather than the library's raw response object.

### Success Criteria:

#### Automated Verification:

- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`
- Unit tests pass: `uv run pytest tests/test_atlassian_client.py`

#### Manual Verification:

- The wrapper module exposes no method whose name or docstring implies a
  write/create/update/delete operation — confirm by reading the module's
  public API surface.

---

## Phase 3: `auth-check` CLI Command

### Overview

A new Typer subcommand that loads the config, builds both read-only clients,
and reports whether each product's credentials are valid — the first
user-facing proof that F-01 works end to end.

### Changes Required:

#### 1. `auth-check` command

**File**: `src/jira_tools/cli.py`

**Intent**: Give the user (and S-01/S-02, once built) a fast way to confirm
Jira + Confluence credentials work before attempting a real fetch, per the
project convention of one `@app.command()` per subcommand in this file.

**Contract**: `jira-tools auth-check` loads the config (Phase 1), builds both
wrapped clients (Phase 2), calls each one's identity check, and prints a
PASS/FAIL line per product (e.g. `Jira: PASS (as <display_name>)` /
`Confluence: FAIL (<reason>)`). Exits with code 0 only if both pass; non-zero
if either fails or the config can't be loaded. Failure reasons come from the
typed exceptions raised in Phases 1–2 and must never include the raw
`api_token` value.

### Success Criteria:

#### Automated Verification:

- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`
- Unit tests pass: `uv run pytest tests/test_cli.py`

#### Manual Verification:

- `uv run jira-tools auth-check --help` shows the command with a clear
  description.
- Running it with a valid config against a real Atlassian Cloud account
  prints PASS for both products.
- Running it with a bad token prints FAIL for both products with a
  human-readable reason, and the terminal output contains no token value.

---

## Phase 4: Testing & Secret-Safety Verification

### Overview

Make the whole auth path testable offline (no live Atlassian credentials
needed in CI or local dev), and add a test that concretely guards the
no-credential-leakage guardrail rather than relying on code review alone.
Document setup for the next person (or agent) who needs to configure this.

### Changes Required:

#### 1. Add test-mocking dependency

**File**: `pyproject.toml`

**Intent**: Enable offline testing of the HTTP calls Phase 2's client wrapper
makes.

**Contract**: Add `responses` to `[dependency-groups].dev` — chosen because
`atlassian-python-api` runs on `requests`, which `responses` mocks directly
(see Critical Implementation Details).

#### 2. Config loader tests

**File**: `tests/test_config.py`

**Intent**: Verify the Phase 1 loader's happy path and its error/warning
paths without touching the real filesystem location.

**Contract**: Tests cover: valid TOML → correctly populated `AtlassianConfig`;
missing file → typed exception naming the expected path; malformed TOML /
missing field → typed exception naming the field; world-readable file
permissions → stderr warning emitted. Use `tmp_path`/monkeypatching to avoid
touching the real `~/.config/jira-tools/`.

#### 3. Client wrapper + `auth-check` tests

**File**: `tests/test_atlassian_client.py`, `tests/test_cli.py`

**Intent**: Verify the identity-check calls succeed/fail correctly against
mocked HTTP responses, and that `auth-check` reports the right PASS/FAIL
combination for each scenario.

**Contract**: Using `responses`, mock the Jira and Confluence identity
endpoints for: both succeed, one fails (401/403), both fail. Assert
`auth-check`'s exit code and printed PASS/FAIL lines match. Add one test that
asserts a known fake token string does not appear anywhere in captured
stdout/stderr across all of the above scenarios — this is the concrete
regression guard for the "no credential leakage" NFR, not just a convention.

#### 4. README setup instructions

**File**: `README.md`

**Intent**: Document how a user gets from "nothing" to a passing
`auth-check` — generating an Atlassian API token, writing the config file,
running the command.

**Contract**: Add a "Configuration" section under "Development" naming the
config file path, its three required fields, a link to
`https://id.atlassian.com/manage-profile/security/api-tokens` for token
generation, and the `uv run jira-tools auth-check` verification step.

### Success Criteria:

#### Automated Verification:

- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`
- Full test suite passes: `uv run pytest`

#### Manual Verification:

- A developer unfamiliar with this change can follow the new README section
  alone to get `auth-check` passing against their own Atlassian Cloud
  account.

---

## Testing Strategy

### Unit Tests:

- Config loading: valid file, missing file, malformed TOML, missing required
  field, permission warning.
- Client wrapper: identity check success and failure (mocked HTTP), per
  product.
- CLI: `auth-check` exit codes and printed output for all pass/fail
  combinations, plus the credential-leakage guard test.

### Integration Tests:

- None automated against live Atlassian — deferred to manual verification
  per phase, since this is a single-user tool without a test Atlassian
  instance in CI.

### Manual Testing Steps:

1. Create `~/.config/jira-tools/config.toml` with real Atlassian Cloud
   credentials; run `uv run jira-tools auth-check`; confirm PASS for both
   products.
2. Temporarily set an invalid `api_token`; re-run; confirm FAIL for both
   products with no token value visible anywhere in the output.
3. Rename the config file away; re-run; confirm the error names the expected
   path and required fields.
4. `chmod 644 ~/.config/jira-tools/config.toml`; re-run; confirm a
   permission warning appears; `chmod 600` and confirm it disappears.

## Performance Considerations

None — this is a single on-demand identity check per product, not a
hot path.

## Migration Notes

Not applicable — no existing credential storage or config to migrate from.

## References

- Roadmap: `context/foundation/roadmap.md` (F-01)
- PRD: `context/foundation/prd.md` (Access Control, NFRs: Read-only, No
  credential leakage)
- Tech stack: `context/foundation/tech-stack.md`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Config & Credential Loading

#### Automated

- [x] 1.1 Type checking passes: `uv run mypy` — 0a63758
- [x] 1.2 Linting passes: `uv run ruff check .` — 0a63758
- [x] 1.3 Unit tests pass: `uv run pytest tests/test_config.py` — 0a63758

#### Manual

- [x] 1.4 Valid config file loads without error — 0a63758
- [x] 1.5 Missing config file produces actionable message naming expected path — 0a63758
- [x] 1.6 Permission warning appears for 644, absent for 600 — 0a63758

### Phase 2: Read-only Atlassian Client Wrapper

#### Automated

- [x] 2.1 Type checking passes: `uv run mypy` — 67c49a3
- [x] 2.2 Linting passes: `uv run ruff check .` — 67c49a3
- [x] 2.3 Unit tests pass: `uv run pytest tests/test_atlassian_client.py` — 67c49a3

#### Manual

- [x] 2.4 Wrapper module's public API exposes no write-implying method — 67c49a3

### Phase 3: `auth-check` CLI Command

#### Automated

- [x] 3.1 Type checking passes: `uv run mypy` — 7f7413c
- [x] 3.2 Linting passes: `uv run ruff check .` — 7f7413c
- [x] 3.3 Unit tests pass: `uv run pytest tests/test_cli.py` — 7f7413c

#### Manual

- [x] 3.4 `--help` shows clear command description — 7f7413c
- [x] 3.5 Valid credentials print PASS for both products — 7f7413c
- [x] 3.6 Invalid credentials print FAIL for both with no token leakage — 7f7413c

### Phase 4: Testing & Secret-Safety Verification

#### Automated

- [x] 4.1 Type checking passes: `uv run mypy` — d9f19c6
- [x] 4.2 Linting passes: `uv run ruff check .` — d9f19c6
- [x] 4.3 Full test suite passes: `uv run pytest` — d9f19c6

#### Manual

- [x] 4.4 An unfamiliar developer can follow the README alone to reach a
      passing `auth-check` — d9f19c6
