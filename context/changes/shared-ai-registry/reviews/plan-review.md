<!-- PLAN-REVIEW-REPORT -->
# Plan Review: Shared AI Tool Registry

- **Plan**: context/changes/shared-ai-registry/plan.md
- **Mode**: Deep
- **Date**: 2026-07-03
- **Verdict**: REVISE → SOUND after triage (all 4 findings fixed in plan, 2026-07-03)
- **Findings**: 0 critical, 2 warnings, 2 observations

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| End-State Alignment | WARNING (see F1) |
| Lean Execution | PASS |
| Architectural Fitness | WARNING |
| Blind Spots | WARNING |
| Plan Completeness | WARNING |

## Grounding

8/8 existing plan-referenced paths ✓ (`skills/`, `rules/`, `install.py` are to-be-created, not yet present — expected). `REQUIRED_FIELDS = ("site_url", "email", "api_token")` confirmed at `config.py:12`. Entry point `jira-tools = "jira_tools:main"` confirmed at `pyproject.toml:18`. Brief↔plan consistent. Progress↔Phase mechanical scan clean (one `## Progress`, all phases/criteria mapped, no stray checkboxes in phase bodies). Phase 3 README check `! grep -qxE "\s*token\s*=.*"` is correct (`-x` anchors whole line; `api_token = ...` won't match) — not a finding.

## Findings

### F1 — Three overlapping install mechanisms; manual path silently drops memory injection

- **Severity**: ⚠️ WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Architectural Fitness (with End-State consequence)
- **Location**: Phase 1 change #3; Phase 3 change #1 item 3; `installation-steps:15`
- **Detail**: The plan's principle is "interactive → agent, mechanical → script" (Implementation Approach). Skill copy is mechanical, so `install.py` owns it — yet three mechanisms install skills: (a) `installation-steps` step 4 "Install the skill files from skills/ to ~/.claude/skills." — a *manual* copy; (b) `install.py` — copies skills AND injects the memory block; (c) Phase 3 bootstrap prompt "then run uv run python install.py". Phase 1 change #3 only says to "confirm step 4 points at skills/", preserving the manual copy and contradicting the architecture. This is a promise gap, not just redundancy: the memory-block injection (Desired End State points 4–5) lives ONLY in `install.py`. `installation-steps` ends at step 4 with no `install.py` and no marker block. Phase 3 change #1 item 3 defines "Manual install" as "the human-readable version of installation-steps" — so the manual path yields skills-but-no-global-memory, an incomplete setup dropping half the stated end state.
- **Fix**: Make `install.py` the single mechanical installer (skills + memory). Rewrite `installation-steps` step 4 to "run `uv run python install.py`" (not "confirm it points at skills/"). The README manual path then inherits full setup for free; the bootstrap prompt's separate `install.py` call becomes a harmless idempotent no-op — note it so the implementer doesn't leave two live copies.
  - Strength: Restores the interactive/mechanical split; closes the end-state promise gap on every install path with one edit.
  - Tradeoff: Phase 1 change #3 becomes a rewrite of step 4, not a one-word field fix — slightly more Phase 1 work.
  - Confidence: HIGH — verified `installation-steps:15` is a manual copy with no injection step, and `install.py` is specced to do both.
  - Blind spot: None significant.
- **Decision**: FIXED (Fix in plan) — Phase 1 change #3 now rewrites step 4 to run `install.py`; noted the bootstrap+step-4 double-call is an idempotent no-op.

### F2 — Phase 1 automated check `! grep -qw "token"` will always fail

- **Severity**: ⚠️ WARNING
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Phase 1 Success Criteria / Progress 1.4
- **Detail**: The check is `grep -q "api_token" ... && ! grep -qw "token" ...`. `installation-steps:11` reads "* token -- an access token -- instruct...". Even after renaming the config field `token` → `api_token`, the prose "access token" still contains the standalone word "token", so `! grep -qw "token"` fails. Verified empirically: `printf '... api_token -- an access token ...' | grep -qw token` → MATCHES. The phase can never pass its own automated gate.
- **Fix**: Scope the negative check to the config-field bullet, e.g. `! grep -qE '^\s*\*\s*token\b' installation-steps` (asserts no bullet begins with a bare `token` field).
- **Decision**: FIXED (Fix in plan) — updated Success Criteria + Progress 1.4 with the scoped grep; also made change #3 explicit that the config.toml field the CLI requires is `api_token` (`config.py:12`), so the checklist must instruct creating an `api_token` entry.

### F3 — Skill copy is run-twice-idempotent but not source-mirroring

- **Severity**: 📋 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Blind Spots
- **Location**: Phase 2 change #3
- **Detail**: "replace-in-place so re-runs update" via `copytree(dirs_exist_ok=True)` satisfies run-twice-same-result, but a file deleted upstream (e.g. a future `references/` file removed) lingers in `~/.claude/skills/`. Fine for today's single-file skill; a latent stale-file hazard once skills grow.
- **Fix**: `rmtree` the target skill dir before copying (mirror source), or state the merge behavior explicitly as a known limitation.
- **Decision**: FIXED (Fix in plan) — Phase 2 change #3 now specifies remove-then-copy (mirror source); added a stale-file test case to change #4.

### F4 — Plan mislocates the "this repo's" narration at SKILL.md:22

- **Severity**: 📋 OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Plan Completeness
- **Location**: Current State (plan:19–20), Key Discoveries (plan:71), Phase 1 change #2
- **Detail**: The string "this repo's jira-tools CLI" occurs only at `SKILL.md:3` (the description frontmatter). `SKILL.md:22` actually reads "the existing jira-tools CLI" — not repo-specific, arguably fine as-is. Low harm because change #2 already lists both line 3 and line 22, so both get edited anyway.
- **Fix**: Correct the line reference (the "this repo's" text is at :3, not :22), or drop the :22 citation.
- **Decision**: FIXED (Fix in plan) — corrected all three citations (Current State, Key Discoveries, Phase 1 change #2) + the References line: "this repo's" is at `:3` (frontmatter); body prose at `:21–22`.
