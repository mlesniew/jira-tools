# Fetch a Single Jira Ticket as Markdown — Implementation Plan

## Overview

Add a `fetch-ticket <KEY>` CLI command that fetches a Jira ticket's title,
status/type metadata, description, and comments, converts the ADF rich
content to Markdown, and prints the assembled document to stdout. This is
roadmap slice S-01, the first of two independent retrieval primitives
(alongside S-02's Confluence fetch) that the later assembly slice (S-04)
will compose.

## Current State Analysis

The codebase currently has only a `version` and `auth-check` command
(`src/jira_tools/cli.py`). `ReadOnlyJiraClient`/`ReadOnlyConfluenceClient`
(`src/jira_tools/atlassian_client.py`) expose exactly one read method each
(`whoami`) — no ticket-fetching capability exists yet. There is no ADF
conversion module and no ticket/comment pydantic models. `pyproject.toml`
depends only on `atlassian-python-api`, `pydantic`, and `typer`.

`context/changes/fetch-jira-ticket/research.md` (complete, hands-on-verified)
already resolves the one open technical question for this slice: which
ADF→Markdown library to use. It recommends `marklas` as primary (native
`mypy --strict` compliance, single lightweight dependency, purpose-built
`plain=True` best-effort mode, and a hands-on smoke test showing clean
conversion of headings/bold/italic/links/mentions/lists/code, with panels
degrading to a raw `<aside>` HTML block).

## Desired End State

Running `uv run jira-tools fetch-ticket <KEY>` (or the installed `jira-tools`
entry point) against a real Jira Cloud ticket prints a single Markdown
document to stdout: a title heading, a one-line metadata subtitle
(key/status/type), a `## Description` section, and a `## Comments` section
with one dated, attributed subsection per comment — all ADF content
converted to readable Markdown. Fetch failures (ticket not found / not
accessible) print a clean message to stderr and exit non-zero, with no
credential ever appearing in output.

Verify by running the command against a real ticket in the operator's own
Jira Cloud site (using the credentials already validated by `auth-check`)
and comparing the printed Markdown against the ticket as shown in the Jira
UI.

### Key Discoveries:

- `src/jira_tools/atlassian_client.py:46-58` — `ReadOnlyConfluenceClient.whoami`
  already establishes the pattern of calling `self._client.get(path)`
  directly against a raw REST path when the underlying library method isn't
  sufficient — the same pattern this plan uses for manual comment pagination.
- `src/jira_tools/atlassian_client.py:38` — existing precedent for isolating
  an untyped-library quirk behind a single line; not needed for `marklas`
  itself (it ships `py.typed`), but confirms the project's tolerance for one
  isolated `type: ignore` if one turns up during implementation.
- Verified directly (not just from docs): instantiating
  `Jira(url=..., cloud=True)` resolves `resource_url("issue")` to
  `rest/api/2/issue` — matching the `rest/api/2/myself` path already
  hard-coded in `tests/test_atlassian_client.py`. Ticket and comment
  endpoints are therefore `rest/api/2/issue/{key}` and
  `rest/api/2/issue/{key}/comment`.
- Verified directly (source inspection): `Jira.issue_get_comments()` performs
  a single unparameterized `self.get(url)` call — no pagination support.
  Manual pagination must use `self._client.get(url, params={...})` directly.
- `context/changes/fetch-jira-ticket/research.md` — full ADF→Markdown library
  research; `marklas`'s `to_md(adf_dict, plain=True)` is the conversion
  entry point, confirmed via a hands-on smoke test against representative
  ADF content.
- `tests/test_atlassian_client.py` / `tests/test_cli.py` — established
  testing pattern: `responses`-mocked REST calls, one test module per source
  module, `CliRunner` for CLI-level tests.
- `pyproject.toml:10-14` — dependency list; `marklas` needs to be added here.

## What We're NOT Doing

- Fetching Confluence pages (S-02 / `fetch-confluence-page`, FR-002).
- Extracting Jira keys or Confluence links from ticket content (S-03, FR-004).
- One-hop assembly / following any extracted links (S-04, FR-005).
- Writing output to a file on disk (FR-006) — this primitive only prints to
  stdout; file output is explicitly owned by S-04's assembly step.
- Loading the result into a Claude conversation (FR-007 / S-05).
- A gap/skip report (FR-008) — that concept applies to multi-item assembly
  (S-04), not a single explicitly-requested fetch, which either succeeds or
  fails clearly.
- Building a runtime fallback to `atlas-doc-parser` or any other ADF library
  — this plan commits to `marklas` only, per the research's hands-on-verified
  recommendation and the project's "simple/lightweight" brief.
- Any ADF node types or edge cases beyond what `marklas` itself converts —
  best-effort conversion is an accepted v1 NFR; unusual macros/embeds may
  render as raw HTML passthrough or be dropped by the library.
- Fuzzy/prose-based ticket reference detection (deferred to v2 per PRD Open
  Question #1).
- Timezone conversion or reformatting of comment timestamps — the raw ISO
  timestamp Jira returns is displayed as-is.

## Implementation Approach

Three phases, each adding one layer: a pure ADF→Markdown conversion module
with no Jira/Confluence knowledge, a Jira-client extension that fetches and
models a ticket's data (including manual comment pagination), and a
document-assembly function plus the CLI command that wires them together.
Each layer is independently unit-testable, matching the existing
`atlassian_client.py` / `cli.py` test split.

## Critical Implementation Details

### Comment pagination

`Jira.issue_get_comments()` (the library's built-in helper) issues exactly
one unparameterized GET and returns whatever page the API defaults to — it
cannot retrieve more than the first page. `ReadOnlyJiraClient` must instead
call `self._client.get(f"{self._client.resource_url('issue')}/{key}/comment", params={"startAt": ..., "maxResults": ...})`
directly (mirroring the raw-`.get()` pattern already used in
`ReadOnlyConfluenceClient.whoami`), looping and accumulating the `comments`
list from each page until the count collected reaches the response's
`total` field.

### ADF pydantic boundary sequencing

CLAUDE.md requires pydantic models at the ADF boundary and forbids passing
raw dicts across module boundaries — but `marklas.to_md()` itself expects a
raw ADF dict, not a pydantic model. The correct sequencing is: parse the raw
JSON from the Jira API response into `ADFNode` immediately (the one
legitimate boundary-crossing point), pass the validated `ADFNode` between
modules, and only call `.model_dump(mode="json", exclude_none=True)` to
produce a dict again at the single call site inside the `adf.py` conversion
function, immediately before invoking `marklas.to_md()`. No other code
should touch a raw ADF dict.

---

## Phase 1: ADF→Markdown Conversion Module

### Overview

A pure, Jira/Confluence-agnostic module that turns a validated ADF node tree
into a Markdown string, wrapping the `marklas` library.

### Changes Required:

#### 1. Add the `marklas` dependency

**File**: `pyproject.toml`

**Intent**: Make the chosen ADF→Markdown library available to the project.

**Contract**: Run `uv add marklas`; this adds `marklas` (and its own
`mistune` dependency) to `[project.dependencies]` and updates `uv.lock`. No
version pin beyond what `uv add` selects.

#### 2. ADF node model and conversion function

**File**: `src/jira_tools/adf.py` (new)

**Intent**: Define the single loose pydantic model for an ADF node
(per research.md's recommended shape) and a `to_markdown()` function that
converts a validated `ADFNode` to a Markdown string via `marklas`.

**Contract**:
```python
class ADFNode(BaseModel):
    type: str
    content: list["ADFNode"] | None = None
    text: str | None = None
    marks: list[dict[str, object]] = []
    attrs: dict[str, object] = {}
```
`to_markdown(node: ADFNode) -> str` internally does
`marklas.to_md(node.model_dump(mode="json", exclude_none=True), plain=True)`
— the `model_dump` call is the one sanctioned point where the validated
model is turned back into a raw dict, immediately before crossing into the
third-party library (see Critical Implementation Details above). ADF's own
field names (`type`, `content`, `text`, `marks`, `attrs`) already match the
model's field names, so no aliasing is needed.

### Success Criteria:

#### Automated Verification:

- `marklas` added to `pyproject.toml` / `uv.lock`: `uv sync` runs cleanly
- Unit tests pass: `uv run pytest tests/test_adf.py`
- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`

#### Manual Verification:

- Feed the representative ADF sample already used in `research.md`'s
  hands-on smoke test (heading, bold/italic/link/mention paragraph, bullet
  list with inline code, code block, panel) through `to_markdown()` and
  visually confirm the output matches the smoke test's recorded `marklas`
  output.

---

## Phase 2: Jira Ticket Retrieval

### Overview

Extend `ReadOnlyJiraClient` with a `get_ticket()` method that fetches a
ticket's fields and all of its comments (paginated), returning a typed
`JiraTicket` model — with no Markdown conversion or CLI concerns at this
layer.

### Changes Required:

#### 1. Ticket and comment models

**File**: `src/jira_tools/atlassian_client.py`

**Intent**: Typed representation of the subset of a Jira issue this slice
needs (FR-001's title/description/comments, plus a status/type metadata
line per the confirmed scope decision).

**Contract**:
```python
class JiraComment(BaseModel):
    author: str
    created: str
    body: ADFNode

class JiraTicket(BaseModel):
    key: str
    summary: str
    status: str
    issue_type: str
    description: ADFNode | None
    comments: list[JiraComment]
```

#### 2. `ReadOnlyJiraClient.get_ticket`

**File**: `src/jira_tools/atlassian_client.py`

**Intent**: Fetch the ticket's fields via `self._client.issue(key, fields="summary,description,status,issuetype")`,
then fetch *all* comments by paginating the raw comment endpoint (see
Critical Implementation Details), and assemble a `JiraTicket`. Each raw
comment dict's `author.displayName`, `created`, and `body` fields map to
`JiraComment`'s fields. Any non-2xx response (ticket not found / forbidden)
propagates as `requests.exceptions.HTTPError`, unhandled at this layer —
consistent with how `whoami()` already lets `HTTPError` propagate.

**Contract**: `def get_ticket(self, key: str) -> JiraTicket`. No new public
methods beyond this one are added to `ReadOnlyJiraClient` (keeps
`test_wrapper_classes_expose_no_write_implying_method`'s
read-only-surface assertion in `tests/test_atlassian_client.py` accurate —
extend that test's expected method list to include `get_ticket`).

### Success Criteria:

#### Automated Verification:

- Unit tests pass: `uv run pytest tests/test_atlassian_client.py`, including
  a case with comments split across two pages (asserting all comments are
  collected, not just the first page) and a case asserting `HTTPError`
  propagates on a 404/403 response
- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`

#### Manual Verification:

- Using credentials already confirmed via `auth-check`, call
  `ReadOnlyJiraClient(config).get_ticket("<REAL-KEY>")` against a real ticket
  in a Python REPL and confirm the returned model's `summary`, `status`,
  and comment count match what the Jira UI shows for that ticket.

---

## Phase 3: Markdown Document Assembly + CLI Wiring

### Overview

Compose the full ticket document as a Markdown string, and wire a
`fetch-ticket` CLI command that fetches, assembles, and prints it —
degrading to a clean stderr message and non-zero exit on fetch failure.

### Changes Required:

#### 1. Document assembly function

**File**: `src/jira_tools/ticket_document.py` (new)

**Intent**: Given a `JiraTicket`, produce the final Markdown document text —
this is template/layout logic, not content conversion (that's `adf.py`'s
job). Structure: `# <summary>` title, then a metadata line containing the
key, status, and issue type, then a `## Description` section (calling
`adf.to_markdown` on the description, or a placeholder line if the
description is `None`), then a `## Comments` section with one
`### Comment by <author> (<created>)` subsection per comment (each calling
`adf.to_markdown` on the comment body), or a placeholder line if there are
no comments.

**Contract**: `def build_ticket_document(ticket: JiraTicket) -> str`. Pure
function — no network calls, no I/O — matching the read-only-surface
principle already stated at the top of `atlassian_client.py`.

#### 2. `fetch-ticket` command

**File**: `src/jira_tools/cli.py`

**Intent**: Load config, construct `ReadOnlyJiraClient`, call `get_ticket`,
pass the result to `build_ticket_document`, and print it to stdout —
following the same config-loading pattern already used by `auth_check`. On
`ConfigError` or `requests.exceptions.HTTPError`, print a one-line message
to stderr (never the raw exception's request/response internals, to avoid
any incidental credential leakage) and exit with code 1.

**Contract**: `@app.command(name="fetch-ticket")` taking a required
positional `key: str` argument, following the existing `@app.command()`
convention at `cli.py:19` and `cli.py:27`.

### Success Criteria:

#### Automated Verification:

- Unit tests pass: `uv run pytest tests/test_ticket_document.py` covering a
  ticket with both a description and comments, a ticket with no description,
  and a ticket with no comments
- CLI tests pass: `uv run pytest tests/test_cli.py`, covering a successful
  `fetch-ticket <KEY>` invocation (via `responses` mocks) and a 404/403
  failure case asserting stderr message + non-zero exit code
- A token-leakage test analogous to `test_auth_check_never_leaks_token`
  confirms the configured API token never appears in `fetch-ticket`'s
  stdout/stderr on either success or failure
- Full suite green: `uv run ruff check .`, `uv run mypy`, `uv run pytest`

#### Manual Verification:

- Run `uv run jira-tools fetch-ticket <REAL-KEY>` against a real ticket in
  the operator's own Jira Cloud site and visually confirm: the title,
  status/type line, description, and comments (in the right order, correctly
  attributed) render as clean, readable Markdown with no credential ever
  printed.
- Run `uv run jira-tools fetch-ticket <NONEXISTENT-KEY>` and confirm a clean
  error message on stderr with a non-zero exit code, no stack trace.

---

## Testing Strategy

### Unit Tests:

- `adf.py`: representative ADF fixtures (heading, marks on text, lists,
  code block, panel) converting to the expected Markdown fragments.
- `atlassian_client.py`: `get_ticket` success case, multi-page comment
  pagination, and HTTP error propagation — all via `responses` mocks against
  the `rest/api/2/issue/...` paths.
- `ticket_document.py`: document assembly with/without description,
  with/without comments.

### Integration Tests:

- CLI-level (`test_cli.py`): `fetch-ticket` success and failure paths via
  `CliRunner` + `responses` mocks, matching the existing `auth-check` test
  style.

### Manual Testing Steps:

1. Run `fetch-ticket` against a real ticket with a rich description
   (headings, lists, links) and multiple comments; confirm readability.
2. Run `fetch-ticket` against a ticket with an empty description and zero
   comments; confirm the placeholder text renders sensibly.
3. Run `fetch-ticket` against a ticket key that doesn't exist or that the
   operator can't access; confirm a clean failure, not a stack trace.

## Performance Considerations

None beyond what's already noted: comment pagination loops until all pages
are collected, which is bounded by the ticket's actual comment count (no
artificial cap).

## Migration Notes

Not applicable — purely additive; no existing data or behavior changes.

## References

- Research: `context/changes/fetch-jira-ticket/research.md`
- PRD: `context/foundation/prd.md:108-122` (FR-001, FR-003),
  `context/foundation/prd.md:78-97` (US-01)
- Roadmap: `context/foundation/roadmap.md` (S-01)
- Existing patterns: `src/jira_tools/atlassian_client.py`,
  `src/jira_tools/cli.py`, `tests/test_atlassian_client.py`,
  `tests/test_cli.py`

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: ADF→Markdown Conversion Module

#### Automated

- [x] 1.1 `marklas` added to `pyproject.toml` / `uv.lock`: `uv sync` runs cleanly — 8b21b13
- [x] 1.2 Unit tests pass: `uv run pytest tests/test_adf.py` — 8b21b13
- [x] 1.3 Type checking passes: `uv run mypy` — 8b21b13
- [x] 1.4 Linting passes: `uv run ruff check .` — 8b21b13

#### Manual

- [ ] 1.5 Representative ADF sample converts to Markdown matching research.md's recorded `marklas` output

### Phase 2: Jira Ticket Retrieval

#### Automated

- [x] 2.1 Unit tests pass: `uv run pytest tests/test_atlassian_client.py` (incl. multi-page comment pagination and HTTPError propagation)
- [x] 2.2 Type checking passes: `uv run mypy`
- [x] 2.3 Linting passes: `uv run ruff check .`

#### Manual

- [ ] 2.4 `get_ticket()` against a real ticket matches the Jira UI's summary/status/comment count

### Phase 3: Markdown Document Assembly + CLI Wiring

#### Automated

- [ ] 3.1 Unit tests pass: `uv run pytest tests/test_ticket_document.py`
- [ ] 3.2 CLI tests pass: `uv run pytest tests/test_cli.py` (success + 404/403 failure cases)
- [ ] 3.3 Token-leakage test confirms no credential in `fetch-ticket` output on success or failure
- [ ] 3.4 Full suite green: `uv run ruff check .`, `uv run mypy`, `uv run pytest`

#### Manual

- [ ] 3.5 `fetch-ticket <REAL-KEY>` against a real ticket renders clean, correctly-ordered, correctly-attributed Markdown with no credential leakage
- [ ] 3.6 `fetch-ticket <NONEXISTENT-KEY>` fails cleanly with stderr message + non-zero exit, no stack trace
