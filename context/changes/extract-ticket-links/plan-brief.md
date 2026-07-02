# Extract Jira Ticket Keys and Confluence Links — Plan Brief

> Full plan: `context/changes/extract-ticket-links/plan.md`

## What & Why

Add a pure link-extraction capability that, given a fetched Jira ticket or
Confluence page, returns every Jira ticket key, Jira issue-link relationship,
and Confluence page it references. This is roadmap slice S-03 / PRD FR-004 —
the prerequisite-free "link extraction" primitive that the north-star S-04
slice (one-hop context assembly) will later compose with the already-built
`fetch-ticket`/`fetch-page` primitives.

## Starting Point

`fetch-ticket` (S-01) and `fetch-page` (S-02) are both complete: `JiraTicket`
and `ConfluencePage` expose their content as a loose, untyped `ADFNode` tree
(`adf.py`). Nothing in the repo extracts structured references from that
tree today, and Jira's `issuelinks` field (explicit "blocks"/"relates to"
relationships between tickets) isn't even fetched yet.

## Desired End State

A new `extract-links <key-or-page-ID-or-URL>` CLI command fetches the target
via the existing clients and prints a deterministic Markdown summary of every
Jira key, issue-link relation, and Confluence page it references — reusable
as-is by S-04's assembly loop once that slice exists.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Input format | ADF-structural (walk `ADFNode`), not rendered Markdown text | Hrefs are structurally exact in ADF; `JiraTicket`/`ConfluencePage` already expose this shape with zero conversion needed | Plan (user-confirmed) |
| Issue-link fields | Also fetch/model Jira's native `issuelinks` field | User expanded scope beyond ADF-only: directly-linked tickets are often expressed via Jira's link feature, not just in-body mentions | Plan (user-added) |
| CLI exposure | Ship `extract-links` command now, not library-only | S-01/S-02 already provide real fetch clients to demo against, ahead of S-04 | Plan (user-confirmed) |
| Bare key detection | Regex-scan all text for key-shaped tokens, not just linked ones | Serves "extract all Jira ticket keys referenced," including keys Jira never auto-linked | Plan (user-confirmed) |
| Confluence link scope | Match against the configured `site_url` only | Avoids false positives on unrelated external URLs; we can only ever fetch pages on our own site anyway | Plan (user-confirmed) |
| Issue-link metadata | Keep structured `key` + `relation` per issue-link, not flattened into the bare-key list | Preserves data Jira's API already provides for free, useful for later v2 relevance filtering | Plan (user-confirmed) |
| Self-reference filtering | Not done here — S-04's job, since only it knows the target's own key | Keeps this module a pure, context-free parser | Plan |
| Output shape | Typed pydantic models (`TicketLinks`/`PageLinks`), not raw dicts/tuples | Matches CLAUDE.md's "pydantic at the ADF boundary" convention already used throughout the codebase | Plan |

## Scope

**In scope:**
- `JiraIssueLink` model + fetching Jira's `issuelinks` field on `JiraTicket`
- `link_extraction.py`: `extract_ticket_links()` / `extract_page_links()`,
  walking ADF for bare keys, `link`-mark hrefs, and `inlineCard`/`blockCard`/
  `embedCard` urls, matched against the configured Atlassian site
- `links_document.py`: Markdown rendering of extraction results
- `extract-links <key-or-URL>` CLI command

**Out of scope:**
- Actually fetching the linked tickets/pages found (S-04)
- Multi-hop traversal
- Prose-only reference detection with no key/link present (PRD Open Question #1, v2)
- Filtering/weighting issue links by relation type (PRD Open Question #4, v2)
- Parsing a Jira issue URL as CLI input (bare key only, matching `fetch-ticket`'s existing acceptance)
- Any change to `adf.py`'s Markdown rendering

## Architecture / Approach

Three layers, added in dependency order: (1) `atlassian_client.py` gains the
`issuelinks` fetch — genuinely new data, not derivable from ADF; (2) a new
pure `link_extraction.py` walks ADF content once per document, returning
sorted/deduplicated typed results, with issue-links passed through directly
from (1) rather than re-derived; (3) `links_document.py` + a new `cli.py`
command render and expose it, mirroring the exact `fetch-ticket`/`fetch-page`
command shape (`fetch-page`'s identifier-validated-before-network-call
pattern in particular).

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Jira issue-links data model + fetch | `JiraIssueLink` + `JiraTicket.issue_links`, fetched via an expanded `fields=` query | Misreading which of `inwardIssue`/`outwardIssue` pairs with `type.inward`/`type.outward` |
| 2. Link extraction module | `link_extraction.py` with `extract_ticket_links()`/`extract_page_links()` | Getting the exact ADF attribute keys right (`link` mark → `attrs.href`; cards → `attrs.url`) — verified against `marklas`'s own parser, not guessed |
| 3. Markdown summary + CLI wiring | `links_document.py` + `extract-links` command | None significant — closely mirrors the already-proven `fetch-page` command shape |

**Prerequisites:** None (S-03 has no roadmap prerequisite; `fetch-ticket`/`fetch-page` already exist to fetch real data for manual verification).
**Estimated effort:** ~1 session across 3 phases — a single new module plus one small extension to an existing one.

## Open Risks & Assumptions

- Jira's `issuelinks` JSON shape (`type.inward`/`type.outward` + exactly one of `inwardIssue`/`outwardIssue`) is taken from well-established Jira Cloud REST API v3 documentation, not verified against a live response in this repo — worth confirming against a real ticket with at least one issue link during Phase 1 manual testing.
- The Jira-key regex (`[A-Z][A-Z0-9]{1,9}-\d+`) will produce occasional false positives on look-alike tokens (e.g. "ISO-9001") in prose — accepted per the PRD's best-effort NFR, not a defect.

## Success Criteria (Summary)

- `extract-links <ticket-key>` finds bare-text keys, explicit issue links, `issuelinks` relations, and same-site Confluence links, all correctly categorized.
- `extract-links <page-id-or-URL>` finds Jira keys and Confluence links in a page's body.
- Output is deterministic — identical input yields byte-identical output across runs.
