<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Fetch a Single Jira Ticket as Markdown

- **Plan**: context/changes/fetch-jira-ticket/plan.md
- **Scope**: Phase 1-3 of 3 (full plan)
- **Date**: 2026-07-02
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 1 observation

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | WARNING |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | PASS |

## Findings

### F1 — Blanket `<br>` replace can corrupt legitimate code/table content

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: src/jira_tools/adf.py:25-30
- **Detail**: `to_markdown()` does `markdown.replace("<br>", "  \n")` over the *entire* rendered string to fix ADF `hardBreak` nodes (added post-close-out in commit `3ccc7cd`, not in the original plan). Verified against `marklas`'s own source: (1) `marklas`'s code-span/fenced-code renderers do not escape literal `<br>` text, so a comment/description containing literal `` `<br>` `` inside inline or fenced code gets corrupted into a broken code span split across two lines; (2) `marklas`'s table-cell renderer independently uses the literal string `<br>` as its *own* internal encoding for embedded newlines inside code within table cells — unrelated to ADF hardBreak — so this replace also silently breaks table rows containing code with embedded newlines. This is a real, narrow-but-real correctness gap, not a hypothetical. The only existing test (`test_hard_break_converts_to_markdown_line_break_not_raw_html`) covers just the intended case, not the corruption case.
- **Fix A ⭐ Recommended**: Scope the replace so it only touches `<br>` outside fenced code blocks and inline code spans (e.g. split the markdown on triple-backtick fences and backtick spans, replace only in the non-code segments).
  - Strength: Fixes the practical, verified corruption case (literal `<br>` pasted in code) without touching `marklas` internals.
  - Tradeoff: The table-cell-with-embedded-code-newline case goes through a different `marklas` code path (`cell.py`) that isn't a code fence/span at all, so this fix may not fully close that specific sub-case — needs verification against a real ADF table+code sample.
  - Confidence: MED — confirmed the code-span/fence corruption case directly in `marklas` source; less certain the same regex approach fully covers the table-cell case.
  - Blind spot: Haven't confirmed how often real Jira tickets actually contain literal `<br>` text inside code (may be rare in practice).
- **Fix B**: Accept the current blanket replace as a documented best-effort limitation (the plan already treats ADF conversion fidelity as a best-effort v1 NFR for other edge cases).
  - Strength: Zero additional engineering; ships as-is.
  - Tradeoff: A known, real (if narrow) correctness bug remains unfixed and untested.
  - Confidence: MED — depends on how often real tickets trigger it.
  - Blind spot: No data on frequency across real tickets.
- **Decision**: FIXED via Fix A — scoped the `<br>` replace in `to_markdown()` to skip fenced code blocks and inline code spans (`src/jira_tools/adf.py`); added regression test `test_hard_break_conversion_does_not_corrupt_literal_br_in_code`.

### F2 — Malformed Jira responses crash instead of degrading gracefully

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: src/jira_tools/cli.py:60-64 (also src/jira_tools/atlassian_client.py:63-106)
- **Detail**: `get_ticket()`/`_get_all_comments()` do direct key-indexing (`fields["summary"]`, `fields["status"]["name"]`, `page["total"]`, `raw_comment["author"]["displayName"]`, etc.) with no `KeyError`/`TypeError` handling, and raise a bare `ValueError` on a non-dict response. `fetch_ticket` (cli.py:60-64) only catches `HTTPError` — any schema drift or partial-field response from Jira (a 200 with unexpected shape) propagates as an unhandled traceback to the user. This directly contradicts CLAUDE.md's stated guardrail — "degrade gracefully on inaccessible links rather than crashing" — and is inconsistent with the pre-existing `_report()` helper (cli.py:69-76) that `auth-check` already uses, which wraps `whoami()` in a broad `except Exception` and reports failures cleanly per-product.
- **Fix A ⭐ Recommended**: Widen `fetch_ticket`'s except clause to match the `_report()` pattern already used by `auth-check` (broad `except Exception`, same clean one-line stderr message + exit 1).
  - Strength: Directly matches the existing, established pattern in the same file; closes the CLAUDE.md guardrail gap with minimal code.
  - Tradeoff: A broad except can mask a genuine bug (e.g. a `NameError`) as "not found or not accessible," making future debugging harder.
  - Confidence: HIGH — the `_report()` precedent already exists in `cli.py`.
  - Blind spot: None significant.
- **Fix B**: Add explicit response-shape validation (e.g. a pydantic model for the raw issue/comment API payload) at the `atlassian_client` boundary, so malformed responses fail with a specific, typed error `cli.py` can catch precisely.
  - Strength: More precise error semantics; avoids over-broad exception handling.
  - Tradeoff: More code — an extra pydantic layer between the raw JSON and `JiraTicket`.
  - Confidence: MED — haven't scoped exactly how much validation this would require.
  - Blind spot: Unclear if this is proportionate to project's "simple/lightweight" brief.
- **Decision**: FIXED via Fix A — widened `fetch_ticket`'s except clause to `except Exception` in `src/jira_tools/cli.py`, matching the `_report()` pattern; removed the now-unused `HTTPError` import.

### F3 — Comment pagination loop has no hard iteration bound

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: src/jira_tools/atlassian_client.py:90-106
- **Detail**: `while len(comments) < total` only advances if `page["comments"]` is non-empty and `page["total"]` is consistent. A page that reports `total > 0` but returns an empty/short `comments` list (e.g. a rate-limit response shaped like a success, or a server glitch) would leave `len(comments)` short of `total` forever, looping indefinitely — bounded only by the 10s per-request timeout, not by iteration count. Normal pagination and the `total: 0` case terminate correctly; the gap is specifically a page that claims more comments remain but delivers none.
- **Fix**: Break out of the loop (raising an error) if a page returns zero comments while `len(comments) < total`, instead of looping again.
- **Decision**: FIXED — `_get_all_comments()` now raises `ValueError("Comment endpoint returned an incomplete page")` if a page returns zero comments while still short of `total` (`src/jira_tools/atlassian_client.py`); added regression test `test_get_ticket_raises_on_incomplete_comment_page`. This is also now caught gracefully by the F2 fix in `fetch_ticket`.

### F4 — Plan's "Key Discoveries" section is now factually stale

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Adherence
- **Location**: context/changes/fetch-jira-ticket/plan.md (Key Discoveries section) vs. src/jira_tools/atlassian_client.py:80-83
- **Detail**: The plan's "Key Discoveries" section states (as "verified directly") that `Jira(url=..., cloud=True)` resolves the issue endpoint to `rest/api/2/issue`, and pagination should hit `rest/api/2/issue/{key}/comment`. Post-close-out commit `6a1f5ce` ("fetch issue/comment data via API v3, not v2") deliberately overrode this: API v2 returns description/comment bodies as plain wiki-markup, not ADF, breaking `ADFNode` validation on any ticket with real content. The current code correctly forces API v3 via `resource_url('issue', api_version='3')`, verified against a real ticket (SICM-5314) and covered by updated test fixtures. This was the right call, but the plan document itself was never updated, so it now reads as inaccurate history for anyone consulting it later.
- **Fix**: Append a short addendum note to the plan's Key Discoveries section documenting that API v3 (not v2) is required, referencing commit `6a1f5ce`.
- **Decision**: FIXED — appended an addendum bullet to the plan's Key Discoveries section (`context/changes/fetch-jira-ticket/plan.md`) documenting the v2→v3 supersession, referencing commit `6a1f5ce`.

## Notes (no findings — informational)

- All automated success criteria pass as of this review: `uv run ruff check .` (clean), `uv run mypy` (clean, strict), `uv run pytest` (39 passed).
- Manual verification items (1.5, 2.4, 3.5, 3.6 in Progress) remain unchecked in the plan pending a real Jira ticket walkthrough — expected, not a defect.
- Plan drift review found no MISSING items; all planned files/models/functions exist as specified. The `get_ticket()` implementation bypasses the library's `issue()` convenience method in favor of a manually-built URL — a deliberate, tested, and necessary consequence of the API v2→v3 fix (see F4), not an accidental regression.
- `ADFNode.marks`/`attrs` keep raw `dict[str, object]` shapes rather than per-type sub-models — defensible given ADF marks/attrs are genuinely open-ended, and `ADFNode` itself is the pydantic boundary type per CLAUDE.md's rule. Not flagged as a violation.
