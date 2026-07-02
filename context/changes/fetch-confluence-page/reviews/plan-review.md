<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Fetch a Single Confluence Page as Markdown

- **Plan**: context/changes/fetch-confluence-page/plan.md
- **Mode**: Deep
- **Date**: 2026-07-02
- **Verdict**: REVISE
- **Findings**: 1 critical, 1 warning, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | PASS |
| Blind Spots | WARNING |
| Plan Completeness | FAIL |

## Grounding

6/6 paths ✓ (`atlassian_client.py`, `cli.py`, `ticket_document.py`, `adf.py`,
`tests/test_atlassian_client.py`, `tests/test_cli.py`), 5/5 symbols ✓
(`resource_url`, `expected_public_methods[ReadOnlyConfluenceClient]`,
`ADFNode`, `build_ticket_document`, `ReadOnlyConfluenceClient`),
brief↔plan ✓.

Also verified two riskier technical claims directly against the installed
`atlassian-python-api` and `marklas` library source (no contradictions
found):
- Confluence's wrapped `get_page_by_id()` only hits the legacy v1 content
  API; no library method wraps `GET /wiki/api/v2/pages/{id}` with
  `body-format` decoding, so the plan's raw `self._client.get(...)` call is
  necessary — confirmed via `atlassian/confluence/__init__.py:360-397`.
- `marklas`'s ADF parser (`marklas/adf/parser.py:95-142`) gracefully drops
  unrecognized *block* node types (returns `None`, filtered out) rather than
  raising, and explicitly supports `extension`/`bodiedExtension`/
  `layoutSection` (Confluence macro/layout nodes) — so richly-formatted
  Confluence pages are not expected to crash the conversion path. (Unknown
  *mark* types do raise `ValueError` at parser.py:76-78, but the mark
  vocabulary already covers the full ADF spec and this code path is shared
  with the already-shipped `fetch-jira-ticket`, so it's an existing,
  already-accepted risk, not a new one introduced by this plan.)

## Findings

### F1 — Phase bodies duplicate numbered checkboxes instead of plain bullets

- **Severity**: ❌ CRITICAL
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 Success Criteria (plan.md:194-206), Phase 2 Success
  Criteria (plan.md:249-268)
- **Detail**: Both phases' `#### Automated Verification:` / `#### Manual
  Verification:` sections use numbered `- [ ] 1.1 ...` / `- [ ] 2.1 ...`
  checkboxes — identical in form to the `## Progress` section at the bottom.
  The project's established convention (confirmed against the sibling
  `fetch-jira-ticket/plan.md`, which shipped cleanly) is: Phase bodies use
  plain `- ` bullets with no numbering/checkbox syntax; only `## Progress`
  gets numbered `- [ ]`/`- [x]` items. See `fetch-jira-ticket/plan.md:186-197`
  for the correct pattern (e.g. `- Unit tests pass: uv run pytest
  tests/test_adf.py` in the phase body vs. `- [x] 1.2 Unit tests pass: ... —
  8b21b13` in Progress). Tooling that parses the Progress section for status
  tracking could be confused by an identical-looking checkbox list appearing
  twice in the document.
- **Fix**: Strip `[ ]` and the `N.M` numbering from every bullet in the two
  Phase-body Success Criteria sections, leaving plain `- ` bullets (text
  unchanged). Leave `## Progress` exactly as-is — it's already correctly
  formatted.
- **Decision**: FIXED

### F2 — Four scope decisions were never confirmed with the user

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: plan-brief.md "Key Decisions Made" table
- **Detail**: Two AskUserQuestion rounds timed out during planning, so the
  plan proceeded on best judgment for: omitting space info, omitting author
  info, accepted URL forms (bare ID + modern pretty URL only, no
  legacy/tiny links), and blogpost handling (no special-case code). The
  plan-brief already flags these explicitly as unconfirmed — this review is
  the natural checkpoint to confirm or override them before Phase 1 starts.
- **Fix**: Confirm each of the four decisions with the user (or explicitly
  accept them as-is) so implementation doesn't have to guess later.
- **Decision**: ACCEPTED — user unavailable for confirmation during this
  triage session; the plan-brief already documents all four as deliberate
  judgment calls with stated rationale (not arbitrary guesses), and this
  review's grounding pass found no contradicting evidence. Proceeding on
  the plan's existing scope; revisit if the user objects before
  implementation starts.
