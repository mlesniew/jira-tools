# Extract Jira Ticket Keys and Confluence Links — Implementation Plan

## Overview

Add a pure link-extraction capability that, given an already-fetched `JiraTicket`
or `ConfluencePage`, returns every Jira ticket key and Confluence page it
references: bare/linked key mentions and Confluence links found in the ADF
content, plus Jira's own structured `issuelinks` relationships (which aren't
fetched today at all). This is roadmap slice S-03 / PRD FR-004 — the
prerequisite-free "link extraction" primitive that S-04's one-hop assembly
will later compose with the existing `fetch-ticket`/`fetch-page` primitives.
The slice ships with its own `extract-links <key-or-URL>` CLI command so it's
independently demoable now, ahead of S-04.

## Current State Analysis

- `JiraTicket` (`src/jira_tools/atlassian_client.py:47-55`) fetches only
  `summary,description,status,issuetype` — Jira's `issuelinks` field (the
  "blocks"/"relates to"/etc. relationships between tickets) is not requested
  or modeled anywhere in the codebase.
- `ADFNode` (`src/jira_tools/adf.py:17-24`) is a loose, untyped model: a
  hyperlink is a `link` **mark** on a text node with `attrs.href`; a
  Jira/Confluence "smart link" is an `inlineCard`/`blockCard`/`embedCard`
  **node** with `attrs.url` and no visible text. Verified directly against
  `marklas`'s own ADF parser (`marklas/adf/parser.py:369,389,401,665` — every
  card type reads `attrs.get("url")`) and against this repo's existing test
  (`tests/test_adf.py:38-46` — the only existing `link`-mark fixture, shape
  `{"type": "link", "attrs": {"href": ...}}`).
- Nothing in the repo has a Jira-key regex today. The only existing
  pattern-extraction precedent is `page_identifier.py:11`
  (`_PAGE_ID_IN_URL = re.compile(r"/pages/(\d+)(?:/|$)")`), used by
  `parse_page_id()` to turn a bare page ID or Confluence pretty-URL into a
  page ID.
- `AtlassianConfig.site_url` (`config.py:18`) already holds the operator's
  single Atlassian Cloud site (shared by Jira and Confluence), which is the
  natural signal for "is this URL actually part of this ticket's context" vs.
  an unrelated external link.
- `cli.py` has one command per file-group following one shape: resolve
  config → fetch via a `ReadOnly*Client` → catch broad `Exception` → clean
  stderr + exit 1 → `typer.echo(build_*_document(...))`. `fetch-page`
  additionally validates its identifier (`parse_page_id`) *before* touching
  the network, failing cleanly with no network call on a bad identifier
  (`tests/test_cli.py:329-338`). `fetch-ticket` accepts only a bare key —
  there is no existing Jira-issue-URL parser to reuse or extend.
- Document assembly (`ticket_document.py`, `page_document.py`) is pure
  template code: a list of Markdown-line strings joined at the end, with
  `*No X.*`-style empty-state constants and `## Section` headings.

## Desired End State

Given a fetched `JiraTicket` or `ConfluencePage`, a new pure function returns
every Jira key, structured issue-link, and Confluence page ID it references.
Running `jira-tools extract-links <KEY-or-page-ID-or-URL>` fetches the target
via the existing clients and prints a deterministic (sorted, stable) Markdown
summary of what it found. Re-running on the same input yields byte-identical
output (barring changes to the underlying ticket/page).

**Verification**: `uv run jira-tools extract-links PROJ-1` against a real
ticket with comments containing a bare key mention, an explicit Jira issue
link (`/browse/...`), an `issuelinks` relationship, and a link to a
Confluence page on the same site prints all of them, correctly categorized.

### Key Discoveries:

- `link` marks and `inlineCard`/`blockCard`/`embedCard` nodes are the only
  two ADF shapes that carry a URL; everything else that looks like a
  reference is a bare string inside a `text` node's `text` field
  (`adf.py:17-24`; `marklas/adf/parser.py:369,389,401,665`).
- Jira's `issuelinks` field is not currently fetched by `get_ticket()`
  (`atlassian_client.py:75-90`) — this must be added to the `fields=` query
  string, not just parsed from an already-available response.
- `page_identifier.parse_page_id()` already implements exactly the
  Confluence-URL-to-page-ID logic this slice needs and raises `ValueError` on
  anything unrecognized — reuse it via try/except rather than duplicating its
  regex.

## What We're NOT Doing

- Actually fetching the linked tickets/pages found (that's S-04's job).
- Multi-hop traversal — this slice only looks at the one document handed to
  it.
- Prose-only reference detection with no key or link present at all (e.g.
  "see the auth epic") — deferred to v2 per PRD Open Question #1.
- Filtering or weighting issue links by relation type (e.g. dropping
  "relates to" as low-signal) — deferred to v2 per PRD Open Question #4. This
  slice captures the relation type as data; it does not act on it.
- Parsing a Jira issue URL (e.g. `.../browse/PROJ-1`) as CLI input for
  `extract-links` — `fetch-ticket` doesn't support this either; a bare key is
  the accepted ticket identifier throughout the CLI today. (Jira browse URLs
  *inside* a document's ADF content are still recognized as key references —
  see Phase 2.)
- Any change to `adf.py`'s Markdown rendering.

## Implementation Approach

Three independently-testable layers, added in dependency order:

1. Extend `atlassian_client.py` to fetch and model Jira's `issuelinks` field
   on `JiraTicket` — this is genuinely new data, not something to derive from
   ADF.
2. A new pure module, `link_extraction.py`, that walks a ticket's/page's ADF
   content plus (for tickets) its `issue_links` field, and returns typed,
   deduplicated, sorted results.
3. A new `links_document.py` (mirroring `ticket_document.py`/
   `page_document.py`) plus `cli.py` wiring for the `extract-links` command.

## Critical Implementation Details

**Exact ADF attribute keys** (verified against `marklas`, not guessed): a
hyperlink is `{"type": "link", "attrs": {"href": "..."}}` as a mark on a
`text` node; `inlineCard`/`blockCard`/`embedCard` nodes carry the URL at
`attrs["url"]` (`None` if absent — skip rather than error).

**Jira `issuelinks` shape**: each entry has a `type` object with `name`,
`inward`, and `outward` phrases, plus *either* an `outwardIssue` *or* an
`inwardIssue` key (never both) — `{"type": {"name": "Blocks", "inward": "is
blocked by", "outward": "blocks"}, "outwardIssue": {"key": "PROJ-2", ...}}`.
The linked key and the human-readable relation phrase come from whichever of
`outwardIssue`/`inwardIssue` is present, paired with `type.outward`/
`type.inward` respectively.

**Determinism (NFR)**: every list in `TicketLinks`/`PageLinks` must be
deduplicated and sorted before being returned, so re-running extraction on
unchanged source data produces byte-identical output.

**Issue links are a passthrough, not an ADF extraction**: `TicketLinks.issue_links`
is copied directly from `JiraTicket.issue_links` (Phase 1's fetch) — it is
*not* re-derived by scanning ADF content in Phase 2. Only `jira_keys` (bare
mentions, `link`-mark hrefs, and card urls) and `confluence_page_ids` come
from walking ADF.

## Phase 1: Jira issue-links data model + fetch

### Overview

Fetch and model Jira's `issuelinks` field, which nothing in the codebase
requests today.

### Changes Required:

#### 1. `JiraIssueLink` model and `JiraTicket.issue_links` field

**File**: `src/jira_tools/atlassian_client.py`

**Intent**: Model a single Jira issue-link relationship (the linked ticket's
key plus the human-readable relation phrase), and add a list of them to
`JiraTicket`, alongside the existing `comments` field.

**Contract**: New `class JiraIssueLink(BaseModel)` with `key: str` and
`relation: str` (see Critical Implementation Details for exactly how
`relation` and `key` are derived from a raw `issuelinks` entry). `JiraTicket`
gains `issue_links: list[JiraIssueLink] = []` — defaulted, matching the
mutable-default pattern already used by `ADFNode.marks`/`attrs` (`adf.py:23-24`),
so existing direct `JiraTicket(...)` construction sites (e.g.
`tests/test_ticket_document.py:16,54,70`) keep working unchanged.

#### 2. Fetch `issuelinks` in `get_ticket()`

**File**: `src/jira_tools/atlassian_client.py`

**Intent**: Request the `issuelinks` field alongside the existing
`summary,description,status,issuetype` fields, and parse the response into
`JiraIssueLink` entries, sorted by `(key, relation)` for determinism.

**Contract**: `_issue_url(key)`'s query string gains `,issuelinks`.
`get_ticket()` reads `fields.get("issuelinks", [])` and builds
`JiraTicket.issue_links` from it, sorted by `(key, relation)` (not `key`
alone — Jira allows more than one relation type between the same two
tickets, and sorting only by `key` wouldn't fully guarantee the plan's own
determinism NFR for that case).

### Success Criteria:

#### Automated Verification:

- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`
- Unit tests pass: `uv run pytest tests/test_atlassian_client.py`

#### Manual Verification:

- None — this phase has no user-facing surface yet (no CLI/document changes).

---

## Phase 2: Link extraction module

### Overview

A new pure module that walks a ticket's or page's ADF content (plus, for
tickets, the `issue_links` fetched in Phase 1) and returns typed, sorted,
deduplicated results.

### Changes Required:

#### 1. `link_extraction.py`

**File**: `src/jira_tools/link_extraction.py` (new)

**Intent**: Define the output shape and the two public entry points
(`extract_ticket_links`, `extract_page_links`) that S-04 and the new CLI
command will call.

**Contract**:
- `class TicketLinks(BaseModel)`: `jira_keys: list[str]`,
  `issue_links: list[JiraIssueLink]`, `confluence_page_ids: list[str]`.
- `class PageLinks(BaseModel)`: `jira_keys: list[str]`,
  `confluence_page_ids: list[str]` (Confluence pages have no `issuelinks`
  concept).
- `def extract_ticket_links(ticket: JiraTicket, site_url: str) -> TicketLinks`:
  walks `ticket.description` and every `comment.body`, unions the found
  `jira_keys`/`confluence_page_ids`, and sets `issue_links` from
  `ticket.issue_links` directly (see Critical Implementation Details).
- `def extract_page_links(page: ConfluencePage, site_url: str) -> PageLinks`:
  walks `page.body` only.

#### 2. ADF-walking internals

**File**: `src/jira_tools/link_extraction.py`

**Intent**: Recursively walk an `ADFNode` tree once, collecting both
categories of reference in a single pass:
  - A `text` node's `text` is regex-scanned for bare Jira-key-shaped tokens
    (`[A-Z][A-Z0-9]{1,9}-\d+`), regardless of whether it also carries a
    `link` mark.
  - A `link` mark's `attrs.href`, and an `inlineCard`/`blockCard`/`embedCard`
    node's `attrs.url`, are checked against `site_url` (same host, via
    `urllib.parse.urlsplit(...).netloc`, case-insensitive): a `/browse/<KEY>`
    path yields a Jira key; anything `page_identifier.parse_page_id()`
    accepts (call it in a `try`/`except ValueError`) yields a Confluence page
    ID. URLs on a different host, or matching neither pattern, are ignored.

**Contract**: One internal recursive helper, e.g.
`_walk(node: ADFNode | None, site_url: str) -> tuple[set[str], set[str]]`
returning `(jira_keys, confluence_page_ids)`, called once per ADF root
(`description`, each comment body, or `page.body`) and unioned by the public
functions above. Both public functions sort every returned list before
constructing their result model (determinism).

### Success Criteria:

#### Automated Verification:

- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`
- Unit tests pass: `uv run pytest tests/test_link_extraction.py`

#### Manual Verification:

- None — covered by Phase 3's manual verification, which exercises this
  module end-to-end via the CLI.

---

## Phase 3: Markdown summary + CLI wiring

### Overview

Render extraction results as Markdown and expose them via a new
`extract-links` CLI command, following the existing `fetch-ticket`/
`fetch-page` pattern.

### Changes Required:

#### 1. `links_document.py`

**File**: `src/jira_tools/links_document.py` (new)

**Intent**: Render a `TicketLinks` or `PageLinks` result as a readable
Markdown document, mirroring `ticket_document.py`/`page_document.py`'s
list-of-lines-joined-at-the-end style, with `## Jira keys` / `## Issue
links` / `## Confluence pages` sections and `*No X found.*`-style empty
states.

**Contract**: `def build_links_document(source: str, result: TicketLinks |
PageLinks) -> str`, where `source` is the key/page-ID that was queried (for
the document's title/heading). An `issue_links` section is only rendered for
`TicketLinks` (a `PageLinks` result has no such field).

#### 2. `extract-links` CLI command

**File**: `src/jira_tools/cli.py`

**Intent**: Accept a bare Jira key or a Confluence page ID/URL, fetch the
matching item via the existing `ReadOnlyJiraClient`/`ReadOnlyConfluenceClient`,
run the appropriate extraction function, and print the rendered document —
following the exact config-load → fetch → catch/report → `typer.echo` shape
of `fetch_ticket`/`fetch_page`.

**Contract**: `@app.command(name="extract-links")` taking one `identifier:
str` argument. Disambiguation: if `identifier` fully matches the Jira-key
pattern (reuse the same regex `link_extraction.py` uses internally — export
it or a small `is_jira_key()` helper from `link_extraction.py` so `cli.py`
doesn't duplicate the pattern), treat as a ticket; otherwise attempt
`parse_page_id(identifier)` and treat as a page; if neither matches, fail
before any network call with a `ValueError`-derived message (mirroring
`fetch_page`'s existing bad-identifier-before-network-call behavior).

### Success Criteria:

#### Automated Verification:

- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`
- Full test suite passes: `uv run pytest`

#### Manual Verification:

- `uv run jira-tools extract-links <real-ticket-key>` against a real ticket
  containing a bare key mention, an explicit `/browse/...` link, an
  `issuelinks` relationship, and a Confluence page link all print correctly
  under their respective sections.
- `uv run jira-tools extract-links <real-confluence-page-id-or-URL>` prints
  Jira keys and Confluence links found in that page's body, with no
  `## Issue links` section.
- Running the same command twice in a row produces identical output.
- An unrecognized identifier (e.g. `not-a-real-identifier`) fails with a
  clean stderr message and exit code 1, with no network call and no
  traceback.

---

## Testing Strategy

### Unit Tests:

- `link_extraction.py`: bare key in plain text; `link`-mark href to a
  same-site Jira issue; `link`-mark href to a same-site Confluence page;
  `link`-mark href to an unrelated external site (ignored); `inlineCard`/
  `blockCard`/`embedCard` with a Jira/Confluence url; a card with `url:
  None` (skipped, no crash); duplicate mentions across description +
  multiple comments (deduplicated); empty/`None` description; sorted output
  ordering.
- `atlassian_client.py`: `get_ticket()` with an `outwardIssue` link, an
  `inwardIssue` link, multiple links, and no `issuelinks` field at all
  (empty list, not a crash).
- `links_document.py`: a `TicketLinks` with all three categories populated;
  a `PageLinks` (no issue-links section); all-empty results render the
  "none found" states rather than empty headings.

### Integration Tests:

- `cli.py`: `extract-links <key>` end-to-end against mocked Jira responses
  (issue + comments, including an `issuelinks` entry); `extract-links
  <page-id-or-URL>` end-to-end against a mocked Confluence response; bad
  identifier fails before any `responses`-mocked call is hit; token-leakage
  check on both success and failure paths (matching the existing
  `never_leaks_token` pattern in `test_cli.py`).

### Manual Testing Steps:

1. Run `extract-links` against a real ticket with a mix of bare-key mentions,
   explicit issue links, `issuelinks` relations, and a Confluence page link.
2. Run `extract-links` against a real Confluence page containing a Jira
   smart-link and a link to another Confluence page.
3. Re-run the same command twice and confirm identical output.

## Performance Considerations

None — this operates on already-fetched, in-memory ADF trees of ticket/page
size; no additional network calls beyond the one fetch already required.

## Migration Notes

Not applicable — `JiraTicket.issue_links` is a new field, defaulted to `[]`
(see Phase 1 contract), so existing direct `JiraTicket(...)` construction
sites need no changes; adding it is additive.

## References

- Related research: `context/changes/fetch-jira-ticket/research.md` (ADF
  node-type survey, `link`-mark/`inlineCard` shapes)
- Similar implementation: `src/jira_tools/page_document.py`,
  `src/jira_tools/ticket_document.py`, `src/jira_tools/cli.py:70-94`
  (`fetch_page`, the closest existing command shape — identifier parsing
  before any network call)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Jira issue-links data model + fetch

#### Automated

- [x] 1.1 Type checking passes: `uv run mypy` — cd88898
- [x] 1.2 Linting passes: `uv run ruff check .` — cd88898
- [x] 1.3 Unit tests pass: `uv run pytest tests/test_atlassian_client.py` — cd88898

### Phase 2: Link extraction module

#### Automated

- [x] 2.1 Type checking passes: `uv run mypy` — 83853ea
- [x] 2.2 Linting passes: `uv run ruff check .` — 83853ea
- [x] 2.3 Unit tests pass: `uv run pytest tests/test_link_extraction.py` — 83853ea

### Phase 3: Markdown summary + CLI wiring

#### Automated

- [x] 3.1 Type checking passes: `uv run mypy` — 2743abf
- [x] 3.2 Linting passes: `uv run ruff check .` — 2743abf
- [x] 3.3 Full test suite passes: `uv run pytest` — 2743abf

#### Manual

- [ ] 3.4 `extract-links <real-ticket-key>` prints bare key, `/browse/...`
      link, `issuelinks` relation, and Confluence page link correctly
      categorized
- [ ] 3.5 `extract-links <real-confluence-page-id-or-URL>` prints Jira keys
      and Confluence links with no `## Issue links` section
- [ ] 3.6 Running the same command twice produces identical output
- [ ] 3.7 An unrecognized identifier fails cleanly (stderr + exit 1, no
      network call, no traceback)
