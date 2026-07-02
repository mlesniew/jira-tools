<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Extract Jira Ticket Keys and Confluence Links

- **Plan**: context/changes/extract-ticket-links/plan.md
- **Mode**: Deep
- **Date**: 2026-07-02
- **Verdict**: SOUND (REVISE at time of review, both findings fixed during triage)
- **Findings**: 1 critical, 1 warning, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | FAIL (both findings fixed during triage) |
| Plan Completeness | PASS |

## Grounding

Grounding: 7/7 paths ✓, 5/5 symbols ✓, brief↔plan ✓

Paths checked: `src/jira_tools/atlassian_client.py`, `src/jira_tools/adf.py`,
`src/jira_tools/page_identifier.py`, `src/jira_tools/config.py`,
`src/jira_tools/cli.py`, `src/jira_tools/ticket_document.py`,
`src/jira_tools/page_document.py`. Symbols checked: `JiraTicket`, `ADFNode`,
`parse_page_id`, `AtlassianConfig.site_url`, `fetch_page`. Also verified
`marklas`'s ADF parser directly (`.venv/.../marklas/adf/parser.py`) confirms
`link`-mark and card-node URL attrs read from `attrs.get("url")`, and cross-checked
roadmap/PRD citations (S-03, FR-004, Open Questions #1/#4) against
`context/foundation/roadmap.md` and `context/foundation/prd.md`.

## Findings

### F1 — Migration Notes claim is false: adding `issue_links` breaks 3 existing test fixtures

- **Severity**: ❌ CRITICAL
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1, Change #1 / Migration Notes
- **Detail**: Migration Notes stated `JiraTicket.issue_links` was purely additive
  with no existing callers to update. Grepping every `JiraTicket(` construction
  site in the repo found `tests/test_ticket_document.py:16,54,70` constructing
  `JiraTicket(...)` directly (not via `get_ticket()`) without an `issue_links`
  argument — Phase 1's contract gave the field no default, so these three
  fixtures would fail with a pydantic `ValidationError` once implemented. Phase
  1's own success criteria only run `pytest tests/test_atlassian_client.py`, so
  the break wouldn't surface until Phase 3's full-suite gate.
- **Fix A ⭐ Recommended**: Give `issue_links` a default of `[]`, matching the
  mutable-default pattern already used by `ADFNode.marks`/`attrs` (`adf.py:23-24`).
  - Strength: Zero changes needed to `tests/test_ticket_document.py`; makes the
    "additive" claim true instead of false.
  - Tradeoff: Diverges from the sibling `comments: list[JiraComment]` field,
    which has no default and is always passed explicitly.
  - Confidence: HIGH — grepped all 3 call sites directly; `adf.py` precedent confirmed.
  - Blind spot: None significant.
- **Fix B**: Keep `issue_links` required (mirror `comments`) and add an explicit
  Phase 1 change item updating the 3 call sites in `tests/test_ticket_document.py`.
  - Strength: Consistent with `comments`' existing required-field style.
  - Tradeoff: Touches a file Phase 1 doesn't currently mention, for a feature
    `ticket_document.py` doesn't use.
  - Confidence: HIGH — same grep evidence as Fix A.
  - Blind spot: None significant.
- **Decision**: FIXED (via Fix A) — `JiraTicket` contract in Phase 1 now specifies
  `issue_links: list[JiraIssueLink] = []`; Migration Notes updated to match.

### F2 — `issue_links` sorted by key alone doesn't guarantee determinism

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 1, Change #2
- **Detail**: Jira allows more than one relationship type between the same two
  tickets (e.g. PROJ-1 "blocks" PROJ-2 and also "relates to" PROJ-2). Sorting
  `issue_links` by `key` alone leaves same-key entries in whatever order the
  Jira API returned them, which the plan's own determinism NFR doesn't
  guarantee is stable across calls.
- **Fix**: Sort by `(key, relation)` tuple instead of `key` alone.
- **Decision**: FIXED — Phase 1 Change #2's intent and contract both updated to
  sort by `(key, relation)`.
