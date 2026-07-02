# Fetch a Single Confluence Page as Markdown Implementation Plan

## Overview

Add a `fetch-page <ID-or-URL>` CLI command that fetches a Confluence page's
title and body content and prints it as clean Markdown. This is roadmap
slice S-02 — the second of the two independent retrieval primitives
(alongside `fetch-ticket`, S-01) that the later one-hop assembly slice
(S-04, the product's north star) will compose together.

## Current State Analysis

- `ReadOnlyConfluenceClient` (`src/jira_tools/atlassian_client.py:112-129`)
  exists but exposes only `whoami()` — no page-fetching capability.
- `adf.py`'s `ADFNode` model and `to_markdown()` function are complete,
  tested, and Jira-agnostic (`src/jira_tools/adf.py`) — built for S-01 but
  designed with no Jira-specific knowledge, so this slice reuses it verbatim
  with zero changes.
- `ticket_document.py` + the `fetch-ticket` command in `cli.py` establish the
  exact "assemble + wire" pattern this slice mirrors: load config → fetch via
  a typed client method → build a Markdown document → print or fail cleanly.
- No Confluence-specific retrieval, identifier-parsing, or document-assembly
  code exists yet.

## Desired End State

Running `jira-tools fetch-page <ID-or-URL>` against a real Confluence Cloud
page prints one Markdown document to stdout: a title, a metadata line
(page ID/status), the page body converted to Markdown, and a fixed fidelity
note about simplified content. The command accepts either a bare numeric
page ID or a page URL copied from Confluence's UI. Fetch failures (not
found, forbidden, unrecognized identifier) print a clean stderr message and
exit non-zero — no stack traces, no credentials ever in output.

### Key Discoveries:

- **Confluence's ADF body is returned as a JSON-encoded string, not a nested
  object** — verified directly against Confluence Cloud's OpenAPI v2 schema
  (`BodyType.value` is `"type": "string"`). This is the opposite of Jira's
  v3 issue API, where `fields.description` is already a nested ADF object
  (`atlassian_client.py:70,76`). `get_page()` must `json.loads()` the value
  before passing it to `ADFNode.model_validate()`.
- **Only the v2 API (`GET /wiki/api/v2/pages/{id}`) supports
  `body-format=atlas_doc_format`.** The library's wrapped
  `Confluence.get_page_by_id()` calls the legacy v1 content API
  (`rest/api/content/{id}`), which predates ADF-format bodies and only
  supports `body.storage`/`body.view`/etc. `get_page()` must bypass the
  wrapped method and call the v2 endpoint directly via `self._client.get(...)`
  — the same deliberate "raw call for the API version that actually returns
  ADF" pattern `get_ticket()` already uses for Jira's v3 API
  (`atlassian_client.py:80-83`).
- **Blogposts are expected to be excluded without any special-case code.**
  Confluence Cloud's v2 API exposes blogposts under a completely separate
  resource (`/wiki/api/v2/blogposts/{id}`), not under `/pages/{id}`, so a
  blogpost's ID passed to the pages endpoint is expected to 404 — the same
  outcome as, and handled identically to, a nonexistent page. This wasn't
  exercised against a real blogpost ID during planning; if it turns out
  Confluence instead resolves it (content IDs are globally unique), the
  fallback is still acceptable — the user just gets the blogpost's content
  through the same code path, which isn't a correctness problem either way.
- **`status` is a plain string** (verified against the `ContentStatus`
  OpenAPI schema: `enum: [current, draft, archived, historical, trashed,
  deleted, any]`, `type: string`) — unlike Jira's `fields.status`, which is
  an object (`{"name": "..."}`) requiring `fields["status"]["name"]`.
  `response["status"]` can be assigned to `ConfluencePage.status: str`
  directly, no unwrapping needed.
- Confluence's page response returns `spaceId` and `authorId` as opaque
  numeric/account IDs, not human-readable names — resolving either to a
  space key or display name would require a second API call per fetch. Per
  the pattern below, both are omitted from v1 output.

## What We're NOT Doing

- Page comments — FR-002 says "get it as Markdown" without mentioning
  comments, in deliberate contrast to FR-001's explicit "title, description,
  **comments**" for Jira tickets. Comments stay out of `fetch-page`'s scope.
- Space-key or author-name enrichment — both require an extra API call per
  fetch for a field FR-002 doesn't ask for; the metadata line shows only
  title, page ID, and status.
- Legacy `viewpage.action?pageId=` URLs or short `/x/...` tiny links —
  `fetch-page` accepts a bare numeric ID or the current pretty-URL form
  Confluence Cloud actually produces today (`/wiki/spaces/KEY/pages/{id}/...`).
  Older/shortened link forms are a v2 concern if they come up in practice.
- Explicit blogpost detection/rejection code — unnecessary; see Key
  Discoveries above.
- Confluence page fetching's link/relevance filtering, one-hop assembly
  (S-04), file output (FR-006), Claude-conversation loading (FR-007),
  gap/skip reporting (FR-008) — all later slices.
- Any changes to `adf.py` — it is reused as-is.

## Implementation Approach

Two phases, each independently testable, mirroring `fetch-jira-ticket`'s
layering minus the ADF-conversion phase (already built):

1. **Retrieval** — a pure `page_identifier.py` module parses a user-supplied
   ID-or-URL into a bare page ID; `ReadOnlyConfluenceClient` gains
   `get_page()`, returning a typed `ConfluencePage`.
2. **Document assembly + CLI wiring** — `page_document.py` renders a
   `ConfluencePage` into the final Markdown string; `cli.py` gains the
   `fetch-page` command, following `fetch_ticket`'s exact structure (config
   load → fetch → render → print, with the same fail-clean error handling).

## Critical Implementation Details

### ADF body decoding differs from Jira's

`get_page()`'s response has `body.atlas_doc_format.value` as a **string**
containing JSON-encoded ADF, not a dict. The call site needs an explicit
`json.loads(...)` step before `ADFNode.model_validate(...)` — copying
`get_ticket()`'s `ADFNode.model_validate(description)` pattern verbatim here
would silently break (`model_validate` on a raw JSON string, not a dict,
raises a pydantic `ValidationError`), so this is worth a code comment at the
call site, not just a plan note, given how easy it is to miss.

### Page identifier parsing lives outside the client

`get_page(page_id: str)` takes an already-resolved bare numeric ID string —
it has no URL-parsing knowledge, mirroring how `get_ticket(key: str)` takes
an already-valid Jira key. `page_identifier.parse_page_id(identifier: str) -> str`
is the pure function that accepts either a bare-digit string or a URL
containing `/pages/<digits>` (optionally followed by `/` and a title slug,
or end-of-string), and raises `ValueError` naming the unrecognized input
otherwise. `cli.py`'s `fetch_page` command calls it before touching the
network, so a malformed identifier fails fast without ever constructing a
client.

## Phase 1: Confluence page retrieval

### Overview

Add the ability to fetch one Confluence page's title, status, and body ADF
by ID, plus the pure identifier-parsing helper that turns a CLI argument
(bare ID or pretty URL) into that ID.

### Changes Required:

#### 1. Page identifier parsing

**File**: `src/jira_tools/page_identifier.py` (new)

**Intent**: Turn whatever a user pastes — a bare page ID or a Confluence
Cloud page URL — into the bare numeric ID string `get_page()` needs, with a
clear error for anything unrecognized.

**Contract**: `parse_page_id(identifier: str) -> str`. Accepts an all-digit
string as-is. Otherwise looks for `/pages/<digits>` in the string (Confluence
Cloud's current pretty-URL shape, e.g.
`https://example.atlassian.net/wiki/spaces/ENG/pages/12345/Some+Title`) and
returns the captured digits. Raises `ValueError` with a message that quotes
the original `identifier` for anything matching neither shape.

#### 2. Confluence page retrieval

**File**: `src/jira_tools/atlassian_client.py`

**Intent**: Add a `ConfluencePage` pydantic model and a `get_page()` method
to `ReadOnlyConfluenceClient` that fetches a single page's title, status,
and body via the Confluence v2 pages endpoint (the only endpoint that
supports `body-format=atlas_doc_format`), decoding the string-encoded ADF
body per the Critical Implementation Details above.

**Contract**:

```python
class ConfluencePage(BaseModel):
    id: str
    title: str
    status: str
    body: ADFNode | None
```

`get_page(self, page_id: str) -> ConfluencePage` calls
`self._client.get(self._page_url(page_id), params={"body-format": "atlas_doc_format"})`
where `_page_url` builds `api/v2/pages/{page_id}` (mirroring `_issue_url`'s
`resource_url(...)` construction on the Jira client), raises `ValueError` if
the response isn't a dict (mirroring `get_ticket`'s existing guard), and
decodes `response["body"]["atlas_doc_format"]["value"]` via `json.loads`
before `ADFNode.model_validate`, treating a missing/empty value as
`body=None`.

#### 3. Update the write-surface guard test

**File**: `tests/test_atlassian_client.py`

**Intent**: `test_wrapper_classes_expose_no_write_implying_method` hardcodes
each client's expected public method list — it must include `get_page` for
`ReadOnlyConfluenceClient` or it will fail as soon as Phase 1 lands.

**Contract**: Update
`expected_public_methods[ReadOnlyConfluenceClient]` from `["whoami"]` to
`["whoami", "get_page"]`.

### Success Criteria:

#### Automated Verification:

- Unit tests pass: `uv run pytest tests/test_atlassian_client.py`
- `page_identifier.py` unit tests pass (bare ID, pretty URL, unrecognized input) — new `tests/test_page_identifier.py`
- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`

#### Manual Verification:

- `ReadOnlyConfluenceClient(config).get_page(<real page ID>)` against a real Confluence Cloud page returns a `ConfluencePage` whose `body` converts cleanly through `adf.to_markdown()` — confirms the decoded ADF body is a `doc`-rooted tree the existing conversion path already handles, since this is the one assumption the whole module-reuse approach rests on.

---

## Phase 2: Markdown document assembly + CLI wiring

### Overview

Render a `ConfluencePage` into the final Markdown document and wire up the
`fetch-page` command, following `ticket_document.py`/`fetch_ticket`'s
established structure exactly.

### Changes Required:

#### 1. Page document assembly

**File**: `src/jira_tools/page_document.py` (new)

**Intent**: Render a `ConfluencePage` as a self-identifying Markdown
document: title, a one-line ID/status subtitle, the converted body, and a
fixed note that some content (macros/panels/embeds) may have been
simplified — per the roadmap's explicit call to keep that fidelity gap
visible rather than silent (`roadmap.md` S-02 Risk).

**Contract**: `build_page_document(page: ConfluencePage) -> str`, structured
as `# <title>` / `**Confluence page <id>** · <status>` / converted body (or
a `*No content.*` placeholder if `body` is `None`) / a closing fidelity-note
line — same shape as `build_ticket_document`, minus the Comments section.

#### 2. CLI wiring

**File**: `src/jira_tools/cli.py`

**Intent**: Add a `fetch-page` command that loads config, parses the given
identifier, fetches the page, and prints the assembled document — following
`fetch_ticket`'s exact error-handling shape (config errors and
identifier-parse errors go to stderr + exit 1 before any network call;
fetch failures are caught broadly and reported as "not found or not
accessible" without leaking the underlying exception).

**Contract**: `@app.command(name="fetch-page") def fetch_page(identifier: str) -> None`,
importing `parse_page_id` from `page_identifier`, `ReadOnlyConfluenceClient`
(already imported), and `build_page_document` from `page_document`.

### Success Criteria:

#### Automated Verification:

- Unit tests pass: `uv run pytest tests/test_page_document.py`
- CLI tests pass: `uv run pytest tests/test_cli.py -k fetch_page`
- Full suite passes: `uv run pytest`
- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`

#### Manual Verification:

- `jira-tools fetch-page <real page ID>` prints a readable Markdown
  document for a real Confluence Cloud page.
- `jira-tools fetch-page <real page URL copied from the browser>`
  produces the same output as passing the bare ID.
- `jira-tools fetch-page <nonexistent ID>` fails cleanly (stderr
  message + exit 1, no stack trace, no credentials).
- `jira-tools fetch-page not-a-real-identifier` fails cleanly with a
  message naming the bad input, before any network call.

---

## Testing Strategy

### Unit Tests:

- `page_identifier.parse_page_id`: bare digit string, modern pretty URL with
  trailing title slug, modern pretty URL with no trailing slug, and
  unrecognized input (raises `ValueError` naming the input).
- `ReadOnlyConfluenceClient.get_page`: page with a body, page with an empty/
  missing body (`body=None`), not-found (404 → `HTTPError`, mirroring
  `test_get_ticket_raises_on_not_found`).
- `build_page_document`: page with body renders title/subtitle/body/fidelity
  note; page with no body renders the `*No content.*` placeholder.

### Integration Tests:

- CLI `fetch-page` end-to-end via `responses`-mocked HTTP, following
  `test_fetch_ticket_prints_markdown_document`'s shape: mock the v2 pages
  endpoint, invoke `runner.invoke(app, ["fetch-page", "<id>"])`, assert on
  stdout content and exit code.
- Token-non-leakage tests on both success and failure paths, mirroring
  `test_fetch_ticket_never_leaks_token_on_success/failure`.

### Manual Testing Steps:

1. Run `jira-tools fetch-page <ID>` against a real page with rich content
   (headings, lists, a panel) and confirm it converts cleanly.
2. Run the same command with the page's full browser URL instead of the ID
   and confirm identical output.
3. Run against a page ID that doesn't exist (or one you don't have access
   to) and confirm a clean stderr failure, not a stack trace.

## Performance Considerations

None specific — a single HTTP round trip per fetch, the same shape as
`fetch-ticket`'s ticket fetch (comment pagination aside, which doesn't apply
here since comments are out of scope).

## Migration Notes

Not applicable — purely additive; no existing data or schema changes.

## References

- Roadmap slice: `context/foundation/roadmap.md` S-02
  (`fetch-confluence-page`)
- PRD requirements: `context/foundation/prd.md` FR-002, FR-003, US-01
- Sibling implementation (pattern source): `context/changes/fetch-jira-ticket/plan.md`
- ADF conversion research (fully reused, no changes needed):
  `context/changes/fetch-jira-ticket/research.md`
- Existing retrieval pattern: `src/jira_tools/atlassian_client.py:63-109`
  (`get_ticket`, the model this plan's `get_page` mirrors)
- Existing document/CLI pattern: `src/jira_tools/ticket_document.py`,
  `src/jira_tools/cli.py:47-65` (`fetch_ticket`)
- Confluence Cloud v2 OpenAPI spec (verified during planning):
  `GET /pages/{id}` operation, `BodySingle`/`BodyType` schemas — confirms
  `body.atlas_doc_format.value` is a JSON string.

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Confluence page retrieval

#### Automated

- [x] 1.1 Unit tests pass: `uv run pytest tests/test_atlassian_client.py`
- [x] 1.2 `page_identifier.py` unit tests pass (bare ID, pretty URL, unrecognized input) — new `tests/test_page_identifier.py`
- [x] 1.3 Type checking passes: `uv run mypy`
- [x] 1.4 Linting passes: `uv run ruff check .`

#### Manual

- [ ] 1.5 `get_page(<real page ID>)` against a real Confluence Cloud page converts cleanly through `adf.to_markdown()`

### Phase 2: Markdown document assembly + CLI wiring

#### Automated

- [ ] 2.1 Unit tests pass: `uv run pytest tests/test_page_document.py`
- [ ] 2.2 CLI tests pass: `uv run pytest tests/test_cli.py -k fetch_page`
- [ ] 2.3 Full suite passes: `uv run pytest`
- [ ] 2.4 Type checking passes: `uv run mypy`
- [ ] 2.5 Linting passes: `uv run ruff check .`

#### Manual

- [ ] 2.6 `jira-tools fetch-page <real page ID>` prints readable Markdown for a real page
- [ ] 2.7 `jira-tools fetch-page <real page URL>` matches the bare-ID output
- [ ] 2.8 `jira-tools fetch-page <nonexistent ID>` fails cleanly
- [ ] 2.9 `jira-tools fetch-page not-a-real-identifier` fails cleanly before any network call
