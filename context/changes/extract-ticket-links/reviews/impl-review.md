<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Extract Jira Ticket Keys and Confluence Links

- **Plan**: context/changes/extract-ticket-links/plan.md
- **Scope**: Phase 1-3 of 3 (full plan)
- **Date**: 2026-07-02
- **Verdict**: APPROVED
- **Findings**: 0 critical, 1 warning, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

`uv run mypy`, `uv run ruff check .`, `uv run pytest` all pass clean (84 tests,
19 source files). Manual verification steps 3.4-3.7 (plan.md) remain unchecked
and could not be exercised in this environment — no live Atlassian credentials
configured. Pending, not failing.

## Findings

### F1 — issuelinks entry missing both outwardIssue/inwardIssue crashes the whole ticket fetch

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: src/jira_tools/atlassian_client.py:91-101
- **Detail**: `get_ticket()`'s issuelinks parsing assumes every raw entry has
  either `outwardIssue` or `inwardIssue`:
  ```python
  key=raw_link["outwardIssue"]["key"] if "outwardIssue" in raw_link
      else raw_link["inwardIssue"]["key"]
  ```
  If an entry has neither (a plausible Jira shape for a link to an issue the
  caller can't view), this raises `KeyError`. `get_ticket()` runs inside
  `cli.py`'s single broad `try/except`, so the `KeyError` surfaces as "Could
  not fetch ticket PROJ-1: not found or not accessible" — an otherwise
  fully-accessible ticket becomes entirely unreadable because of one
  restricted linked issue. This is the direct opposite of this project's
  stated guardrail ("degrade gracefully on inaccessible links rather than
  crashing" — CLAUDE.md), and contrasts with `link_extraction.py`'s `_walk`,
  which `isinstance`-guards every node defensively. No test exercises a
  partial/malformed issuelinks entry.
- **Fix**: Use `raw_link.get("outwardIssue", {}).get("key")` style guards (or
  an explicit key check) to skip entries missing both `outwardIssue` and
  `inwardIssue` instead of raising, and add a test for a partial issuelinks
  entry.
- **Decision**: FIXED — `get_ticket()` now skips `issuelinks` entries missing
  both `outwardIssue`/`inwardIssue` instead of raising `KeyError`;
  `test_get_ticket_skips_issue_link_missing_both_outward_and_inward_issue`
  added in `tests/test_atlassian_client.py`. 85 tests pass, mypy/ruff clean.

### F2 — `_walk` has no explicit recursion depth guard

- **Severity**: ℹ️ OBSERVATION
- **Impact**: 🏃 LOW — no action needed
- **Dimension**: Safety & Quality
- **Location**: src/jira_tools/link_extraction.py
- **Detail**: A pathologically deep ADF tree would hit
  `ADFNode.model_validate()`'s own recursion first (inside the same
  try/except that wraps `get_ticket`/`get_page`), so `_walk` never gets a
  chance to overflow independently. Noted for completeness only — no fix
  needed.
- **Decision**: SKIPPED — already mitigated upstream by `ADFNode`'s own
  recursive validation inside the same try/except; no independent risk.

## Sub-agent evidence

**Plan Drift Detection**: no drift found. All 8 planned changes across
Phase 1-3 verified MATCH against actual code (models, sort order, passthrough
semantics for `issue_links`, ADF-walk disambiguation order, `is_jira_key()`
reuse in `cli.py`, error-before-network-call behavior). No scope-guardrail
violations (no fetching of linked tickets/pages, no multi-hop traversal, no
browse-URL-as-CLI-arg support, `adf.py` untouched).

**Safety, Quality & Pattern Compliance**: F1 and F2 above. No credential
leakage in any code path (confirmed by existing `never_leaks_token` tests).
No SSRF risk (`_categorize_url` only string-parses URLs, no network calls
against user-influenced hrefs). Read-only surface unchanged. Pattern
compliance clean: `cli.py`'s `extract-links` follows the exact
config-resolve → fetch → catch-Exception → stderr+exit(1) → typer.echo shape
as `fetch_ticket`/`fetch_page`; `links_document.py` mirrors
`ticket_document.py`/`page_document.py`'s list-of-lines + `_NO_*`
empty-state-constant style.
