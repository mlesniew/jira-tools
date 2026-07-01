<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Read-only Atlassian Auth Wired

- **Plan**: context/changes/atlassian-readonly-auth/plan.md
- **Scope**: Phase 1-4 of 4 (full plan)
- **Date**: 2026-07-01
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 3 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | WARNING |
| Pattern Consistency | WARNING |
| Success Criteria | PASS |

## Success criteria verification

- `uv run mypy` — PASS (0 issues, 7 source files)
- `uv run ruff check .` — PASS (all checks passed)
- `uv run pytest` — PASS (22/22 passed)
- All Manual verification items across Phases 1-4 have observable evidence in the diff (config loader error paths, permission-warning test, wrapper public-surface guard test, CLI PASS/FAIL output, README section) — no rubber-stamping detected.
- Plan drift sub-agent found zero DRIFT/MISSING/EXTRA across all 4 phases; every planned change matches its stated contract exactly.

## Findings

### F1 — Latent credential exposure via chained ValidationError

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: src/jira_tools/config.py:66-72
- **Detail**: When the TOML `api_token` field isn't a string (typo, unquoted number, etc.), pydantic's ValidationError embeds the raw value verbatim. Reproduced directly: `api_token = 999999999` in the config file produces a caught `ConfigInvalidError` whose `__cause__` reads "Input should be a valid string ... input_value=999999999". The code does `raise ConfigInvalidError(...) from exc`, preserving that cause. `SecretStr` masking never applies because the failure happens during parsing, before the value becomes a SecretStr. Nothing in the current shipped code renders `__cause__` (CLI only echoes `str(exc)`, and `typer.Exit` swallows the traceback), so this isn't exploitable today — but it's a landmine for the next change: any future `logging.exception()`, error tracker (Sentry captures `__cause__` by default), or a new command calling `load_config()` without the `except ConfigError` guard will leak it. Violates CLAUDE.md's "no credentials in output/logs/cache" guardrail at the source.
- **Fix A ⭐ Recommended**: `raise ConfigInvalidError(...) from None` — suppress cause chaining for this exception entirely.
  - Strength: One-line change; kills the whole leak class regardless of which field is bad or how many error paths this loader grows to.
  - Tradeoff: Loses the underlying pydantic traceback for debugging (minor — ConfigInvalidError's own message already names the offending field).
  - Confidence: HIGH — reproduction confirms this fully suppresses the leak path without touching other behavior; no test asserts on `__cause__`.
  - Blind spot: None significant.
- **Fix B**: Catch specifically for `api_token` and redact its `input_value` before building the message/cause, leaving chaining intact for other fields.
  - Strength: Preserves debuggability for non-secret field errors (site_url, email typos).
  - Tradeoff: More code, and doesn't generalize — any future secret-bearing field needs its own manual carve-out.
  - Confidence: MEDIUM — correct today but a maintenance foot-gun as the schema grows.
  - Blind spot: Haven't checked whether pydantic has a built-in redaction hook for SecretStr-typed fields during validation, which would scale better.
- **Decision**: FIXED (Fix A — `from None`)

### F2 — Layering leak: typer import in config.py

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Architecture
- **Location**: src/jira_tools/config.py:10, 75-81
- **Detail**: `config.py` imports `typer` and calls `typer.echo(..., err=True)` directly from `_warn_if_permissive`, even though CLAUDE.md scopes Typer/CLI concerns to `cli.py` ("CLI commands are defined in cli.py using Typer"). The config loader — meant to be a plain, reusable module — carries a CLI-framework side effect. Not a functional bug today (tests pass via capsys), but any future non-CLI consumer of `load_config()` inherits an unwanted `typer` dependency and stdout/stderr side effect.
- **Fix**: Have `_warn_if_permissive` return the warning as data instead of printing it; let `cli.py`'s `auth_check` decide how to display it via `typer.echo`.
  - Strength: Restores the module boundary CLAUDE.md implies; makes config.py usable without importing Typer.
  - Tradeoff: Touches config.py, cli.py, and both test files that currently assert on capsys output from load_config directly — a real, if mechanical, multi-file edit.
  - Confidence: MEDIUM — direction is clear, but the exact shape (return value on the config? separate return?) isn't prescribed by the plan.
  - Blind spot: Haven't checked whether the upcoming S-01/S-02 (fetch-ticket/fetch-page) will call load_config() directly — if so this pays off soon; if not, lower urgency.
- **Decision**: FIXED — `_warn_if_permissive` replaced by public `permission_warning(path) -> str | None` (pure data, no typer import); `cli.py`'s `auth_check` now resolves the path, checks the warning, and echoes it itself before calling `load_config(path)`. Updated `tests/test_config.py`'s two capsys-based tests to assert on `permission_warning()`'s return value directly.

### F3 — Weak exception assertions in client wrapper tests

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Pattern Consistency
- **Location**: tests/test_atlassian_client.py:47-56, 59-70
- **Detail**: `test_jira_whoami_raises_on_unauthorized` and `test_confluence_whoami_raises_on_unauthorized` use a manual `try/except Exception: pass / else: raise AssertionError(...)` instead of `pytest.raises(...)`, which sibling file test_config.py uses consistently. It's also weaker — accepts any exception type instead of asserting the specific one. Confirmed `atlassian-python-api` raises `requests.exceptions.HTTPError` on non-2xx responses (rest_client.py:978,999).
- **Fix**: Replace both with `with pytest.raises(HTTPError):` to match the pytest.raises idiom used elsewhere and get a stronger assertion.
- **Decision**: FIXED — both tests now use `pytest.raises(HTTPError)`.

## Observations

### O1 — No format validation on site_url/email

- **Location**: src/jira_tools/config.py:19-20
- **Detail**: `site_url`/`email` are plain `str`, no `AnyHttpUrl`/`EmailStr`. A malformed site_url surfaces later as a confusing connection error during auth-check instead of a clear config error. Not a guardrail violation — UX rough edge only.
- **Decision**: SKIPPED

### O2 — Asymmetric response validation between whoami() methods

- **Location**: src/jira_tools/atlassian_client.py:36-39 vs 53-58
- **Detail**: Confluence's whoami() checks isinstance(response, dict) before indexing (mypy-forced, since Confluence.get() is typed as a Union); Jira's whoami() doesn't (Jira.myself() is untyped upstream via `# type: ignore[no-untyped-call]`). Harmless today since cli.py's _report catches any exception — just a defensive-style asymmetry.
- **Decision**: SKIPPED
