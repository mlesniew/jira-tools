# Read-only Atlassian Auth Wired — Plan Brief

> Full plan: `context/changes/atlassian-readonly-auth/plan.md`

## What & Why

Wire read-only authentication to Jira Cloud + Confluence Cloud into the CLI.
This is F-01 on the roadmap — a foundation slice with no user-visible feature
of its own, whose job is to get the credential-safety contract (read-only,
never leaked) right once, before S-01/S-02 build real fetch primitives on top
of it.

## Starting Point

The CLI is a bare Typer scaffold with one `version` command. No auth, HTTP
client, or credential-handling code exists anywhere. `pyproject.toml` only
depends on `pydantic` + `typer`. `acli` (floated as a possible auth shortcut
in `tech-stack.md`) is not installed on this machine and no existing
Atlassian session/credentials were found, so it isn't actually available
without extra setup outside this change.

## Desired End State

A user creates `~/.config/jira-tools/config.toml` with their Atlassian Cloud
site URL, email, and API token, then runs `uv run jira-tools auth-check` to
get a clear PASS/FAIL report per product (Jira, Confluence) — proving
credentials work before any real ticket/page fetch is attempted, with the
token never appearing in output, cache, or logs.

## Key Decisions Made

| Decision                 | Choice                                             | Why (1 sentence)                                                                 |
| ------------------------ | --------------------------------------------------- | ----------------------------------------------------------------------------------- |
| Deployment target        | Atlassian Cloud                                     | Confirmed by user; simplest and most common setup.                                  |
| Auth mechanism           | Atlassian API token (email + token)                 | `acli` isn't installed/available on this machine; API token is the standard Cloud credential. |
| Credential storage       | Config file (`~/.config/jira-tools/config.toml`)    | User's explicit choice over env vars — explicit, inspectable, documented location.  |
| HTTP/client library      | `atlassian-python-api`                              | Purpose-built wrapper for both products, matches the weekend-sized-build goal.      |
| Connection verification  | Dedicated `auth-check` command                      | Gives a fast, explicit way to debug bad credentials before real fetches exist.       |
| Read-only enforcement    | Thin wrapper exposing only read methods              | Makes read-only structurally true for all downstream code, not just a convention.   |
| Testing without live creds | Mocked HTTP via `responses` (not `respx`)          | `atlassian-python-api` runs on `requests`, not `httpx` — `respx` would silently no-op. |

## Scope

**In scope:**
- Config file loading (TOML, XDG-aware path, pydantic model with `SecretStr` token)
- Actionable errors for missing/malformed config; file-permission warning
- Read-only client wrapper around `atlassian-python-api`'s Jira/Confluence classes
- `auth-check` CLI command reporting per-product PASS/FAIL
- Offline tests (mocked HTTP) including an explicit no-leakage regression test
- README setup documentation

**Out of scope:**
- OAuth 2.0 flow, `acli` session reuse, Server/Data Center support
- Interactive setup wizard, OS-keyring storage, token encryption
- Environment-variable credential override
- Any actual ticket/page fetch methods (S-01/S-02's job)

## Architecture / Approach

Four small modules: `config.py` (load + validate credentials),
`atlassian_client.py` (construct clients, expose only read operations),
a new `auth-check` command in the existing `cli.py`, and tests that mock the
`requests`-based HTTP layer so no real Atlassian account is needed to verify
the code. S-01/S-02 will later extend `atlassian_client.py`'s read-only
surface rather than reaching into the underlying library directly.

## Phases at a Glance

| Phase                              | What it delivers                                          | Key risk                                                     |
| ----------------------------------- | ------------------------------------------------------------ | ---------------------------------------------------------------- |
| 1. Config & credential loading      | Typed config model + TOML loader, actionable errors           | Token leaking into an error message or log accidentally           |
| 2. Read-only client wrapper         | `atlassian-python-api` clients wrapped to expose only reads   | Wrapper accidentally re-exposing a write method                   |
| 3. `auth-check` CLI command         | Per-product PASS/FAIL report, correct exit codes               | Failure messages leaking the bad token value                      |
| 4. Testing & secret-safety          | Offline mocked tests + explicit leakage regression test + docs | Using the wrong mock library (`respx` vs `responses`) and getting false-green tests |

**Prerequisites:** User needs a valid Atlassian Cloud account with an API
token (generated at id.atlassian.com) for manual verification steps; no other
external dependency.
**Estimated effort:** ~1 session across 4 phases — foundation-sized, matches
the roadmap's weekend-build budget.

## Open Risks & Assumptions

- Assumes Atlassian Cloud (not Server/Data Center) — confirmed by user; if
  wrong, the auth mechanism and client construction both change.
- Assumes `atlassian-python-api`'s Cloud auth pattern (`username=email,
  password=api_token, cloud=True`) remains the correct call shape for the
  version installed; if a newer major version changes this, Phase 2 absorbs
  the adjustment.

## Success Criteria (Summary)

- `uv run jira-tools auth-check` reports PASS for both Jira and Confluence
  against a real account, and FAIL with a clear reason (no token leakage)
  against bad credentials.
- Missing/malformed config produces an actionable error, not a crash.
- Full automated suite (`ruff`, `mypy`, `pytest`) passes with no live
  Atlassian credentials required.
