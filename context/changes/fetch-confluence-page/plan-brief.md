# Fetch a Single Confluence Page as Markdown — Plan Brief

> Full plan: `context/changes/fetch-confluence-page/plan.md`

## What & Why

Add a `fetch-page <ID-or-URL>` CLI command that fetches a Confluence page's
title and body and prints it as clean Markdown. This is roadmap slice S-02
— the second of the two independent retrieval primitives (FR-002) that the
later one-hop assembly slice (S-04, the product's north star) will compose
together, alongside `fetch-ticket` (S-01).

## Starting Point

`ReadOnlyConfluenceClient` exists but exposes only `whoami()` — no page
fetching yet. The ADF→Markdown conversion module (`adf.py`, built for S-01)
is complete, tested, and Jira-agnostic, so this slice reuses it with zero
changes. The `ticket_document.py` + `fetch-ticket` command pair is the
architectural template this plan mirrors.

## Desired End State

Running `jira-tools fetch-page <ID-or-URL>` against a real Confluence Cloud
page prints one Markdown document: title, a page ID/status subtitle, the
converted body, and a fixed note that some content may have been
simplified. Both a bare numeric page ID and a page URL copied from
Confluence's UI work as input. Not-found/inaccessible pages and unparseable
identifiers fail cleanly (stderr + exit 1), never with a stack trace or
leaked credential.

## Key Decisions Made

Two AskUserQuestion rounds timed out with no response during planning
(the user appears to have been away). The four decisions below were made
using best judgment, grounded in PRD/roadmap signals and the verified
Confluence API shape — **flagged here for explicit review**, not silently
assumed permanent.

| Decision                     | Choice                                             | Why (1 sentence)                                                                                                   | Source | Confirmed? |
| ----------------------------- | ----------------------------------------------------| ---------------------------------------------------------------------------------------------------------------------| -------- | ----------- |
| Space info in output          | Omit entirely                                      | `spaceId` comes back as an opaque ID; resolving it needs an extra API call for a field FR-002 doesn't ask for.       | Plan   | **No — best judgment** |
| Author info in output         | Omit entirely                                      | Same reasoning as space info: `authorId` is opaque, resolving it costs an extra call, not required by FR-002.       | Plan   | **No — best judgment** |
| Blogpost handling             | No special-case code — expected to 404 naturally   | Confluence v2 puts blogposts under a separate `/blogposts/{id}` resource, so a blogpost ID against `/pages/{id}` is expected to 404. Not verified against a real blogpost ID; either outcome (404 or unexpectedly resolving) is acceptable, so no code change either way. | Plan (research) | N/A — not really a choice, a discovered fact |
| URL forms accepted            | Bare ID + modern pretty URL only                    | Covers the URL shape Confluence Cloud actually produces today; legacy/tiny-link forms add parsing/network complexity for a rare case. | Plan   | **No — best judgment** |
| Page comments                 | Out of scope                                       | FR-002 says "get it as Markdown" without mentioning comments, unlike FR-001's explicit "title, description, comments" for tickets. | Plan (PRD signal) | Reasonably high confidence — strong textual contrast in the PRD |
| "Content simplified" note     | Include a fixed footer note                        | Roadmap's S-02 Risk explicitly calls for keeping macro/panel/embed fidelity gaps visible rather than silent.         | Roadmap | Already settled upstream |

## Scope

**In scope:**
- `fetch-page <ID-or-URL>` command
- `page_identifier.py`: pure bare-ID/URL parsing
- `ReadOnlyConfluenceClient.get_page()`: Confluence v2 page retrieval with ADF body decoding
- `page_document.py`: Markdown document assembly
- Error handling for not-found/forbidden pages and unparseable identifiers

**Out of scope:**
- Page comments, space/author name resolution, legacy/tiny-link URL forms
- Explicit blogpost rejection code (unnecessary — see Key Decisions)
- Link extraction (S-03), one-hop assembly (S-04), file output (FR-006),
  Claude-conversation loading (FR-007), gap/skip reporting (FR-008)
- Any changes to `adf.py`

## Architecture / Approach

Two layers, mirroring `fetch-jira-ticket` minus the ADF-conversion phase
(already built): `page_identifier.py` turns a CLI argument into a bare page
ID (no network); `atlassian_client.py` gains `get_page()` returning a typed
`ConfluencePage` (fetches via the Confluence v2 pages endpoint — the only
one that supports `body-format=atlas_doc_format` — and decodes the
JSON-string-encoded ADF body, unlike Jira's already-nested body); `page_document.py`
+ `cli.py` assemble the final document and wire up the command, following
`ticket_document.py`/`fetch_ticket`'s exact shape.

## Phases at a Glance

| Phase                                       | What it delivers                                                    | Key risk                                                                 |
| --------------------------------------------- | ----------------------------------------------------------------------| ----------------------------------------------------------------------------|
| 1. Confluence page retrieval                  | `page_identifier.py` + `get_page()` on `ReadOnlyConfluenceClient`    | The JSON-string ADF body decoding is a real gotcha — easy to miss and silently mis-handle |
| 2. Markdown document assembly + CLI wiring    | `page_document.py` + `fetch-page` command                            | None significant — this phase is a near-direct mirror of the already-proven `fetch-ticket` pattern |

**Prerequisites:** F-01 (`atlassian-readonly-auth`) already merged; S-01
(`fetch-jira-ticket`) already merged — `adf.py` is reused verbatim.
**Estimated effort:** ~1 session across 2 phases; smaller than S-01 since
the ADF conversion module needs no new work.

## Open Risks & Assumptions

- **The four "best judgment" decisions above were not confirmed by the
  user** — review them before or during implementation; they're easy to
  flip (each is a small, isolated piece of the plan) if the actual
  preference differs.
- Assumes the decoded ADF body from a Confluence page is a `doc`-rooted tree
  compatible with the existing `adf.to_markdown()` path built for Jira —
  near-certain (same ADF spec) but not yet verified against a real page;
  Phase 1's manual verification step is the explicit gate for this.
- Assumes Confluence Cloud (not Data Center) — consistent with F-01's
  existing auth setup and this plan's use of the v2 API, which is
  Cloud-only.

## Success Criteria (Summary)

- `jira-tools fetch-page <ID-or-URL>` against a real page produces clean,
  correctly-structured Markdown, working identically whether given a bare
  ID or a copied browser URL.
- Fetching a nonexistent/inaccessible page or an unparseable identifier
  fails cleanly (stderr + exit 1), never with a stack trace or leaked
  credential.
- Full check suite (`ruff`, `mypy --strict`, `pytest`) passes.
