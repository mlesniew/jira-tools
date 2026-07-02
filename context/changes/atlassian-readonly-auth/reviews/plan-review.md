<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Read-only Atlassian Auth Wired

- **Plan**: context/changes/atlassian-readonly-auth/plan.md
- **Mode**: Deep (retrospective — plan was already fully implemented and impl-reviewed prior to this review)
- **Date**: 2026-07-02
- **Verdict**: SOUND (after fixes)
- **Findings**: 0 critical, 3 warnings, 0 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | PASS |
| Lean Execution | PASS |
| Architectural Fitness | WARNING |
| Blind Spots | WARNING |
| Plan Completeness | PASS |

## Grounding

8/8 paths ✓ (cli.py, config.py, atlassian_client.py, pyproject.toml, test_config.py, test_atlassian_client.py, test_cli.py, README.md), 5/5 symbols ✓ (AtlassianConfig, SecretStr, ReadOnlyJiraClient, ReadOnlyConfluenceClient, auth-check), brief↔plan ✓. Mechanical Progress↔Phase contract checked clean (single `## Progress` heading, all 4 phases matched, no stray checkboxes outside Progress). Blast-radius sweep found no callers of load_config/permission_warning/client wrappers outside cli.py and tests.

## Findings

### F1 — Secret-redaction contract didn't anticipate pydantic's exception chaining

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Blind Spots
- **Location**: Phase 1 — Config & Credential Loading, plan.md (Contract, config loader)
- **Detail**: The Phase 1 contract said malformed/missing fields should raise a typed exception "without echoing the rest of the file's contents," but didn't name the mechanism needed to satisfy that against pydantic's `ValidationError`, which embeds the raw offending value and gets carried forward via default `raise ... from exc` chaining even when the wrapping exception's own message is clean. This is exactly the credential-leak-shaped bug impl-review caught and fixed as its own F1 (`config.py:66-72`, fixed via `raise ... from None`). Code was already correct; only the plan text was stale.
- **Fix**: Added explicit requirement to Phase 1's Contract to wrap validation errors with `raise ConfigInvalidError(...) from None`, naming pydantic's chaining behavior as the reason.
- **Decision**: FIXED (plan text updated to match shipped code; no code change needed)

### F2 — Phase 1 contract puts a Typer call inside config.py

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Architectural Fitness
- **Location**: Phase 1 — Config & Credential Loading, plan.md (Contract, config loader)
- **Detail**: The Contract directed `config.py` to "emit a `typer.echo` warning (to stderr)" directly, contradicting CLAUDE.md's convention that Typer/CLI concerns live in `cli.py`. Impl-review caught this as its own F2 and fixed it: `config.py` now exposes `permission_warning(path) -> str | None` (pure data), and `cli.py` calls `typer.echo` with it. Discussed alternatives (raising an exception, using `warnings.warn()`) during triage — both rejected as more machinery for no benefit given this is a simple local tool (YAGNI): exceptions are wrong for a non-fatal advisory condition and would couple permission-checking to config parsing; `warnings.warn()`'s default per-location filter dedup and output-format mismatch would need extra code to work around, for a single call site.
- **Fix**: Rewrote the contract to say `config.py` returns the warning as data (`str | None`) and `cli.py` (Phase 3) decides how to display it.
- **Decision**: FIXED (plan text updated to match shipped code; no code change needed)

### F3 — No timeout/hang behavior specified for auth-check

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 2 — Read-only Atlassian Client Wrapper, plan.md (Contract, read-only client wrapper)
- **Detail**: Neither the plan nor the shipped code set an explicit `timeout` on the `Jira`/`Confluence` constructors. `atlassian-python-api` defaults to `timeout=75` seconds — not infinite, but a 75-second silent freeze is rough UX for a command the plan's own Overview calls "a fast way to confirm credentials" (e.g. a typo'd `site_url` pointing at a dead host). Unlike F1/F2, this was a genuinely open gap, not something impl-review had already fixed.
- **Fix**: Added `timeout=10` to Phase 2's Contract and to both constructors in `src/jira_tools/atlassian_client.py`. Verified with `uv run ruff check .`, `uv run mypy`, `uv run pytest` — all pass (22/22 tests).
- **Decision**: FIXED (plan text + code both updated)
