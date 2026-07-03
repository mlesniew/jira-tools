# Shared AI Tool Registry — Plan Brief

> Full plan: `context/changes/shared-ai-registry/plan.md`
> Research: `context/changes/shared-ai-registry/research.md`

## What & Why

Turn `jira-tools` into the team's shared AI tool registry so teammates get the
CLI **and** the skills that use it from one source of truth, instead of copying
artifacts between repos. The repo *is* the package — distributed by `git clone`
plus a copy-paste bootstrap prompt, deliberately skipping the npm/PyPI registry
layer (confirmed acceptable with the course organizers).

## Starting Point

Today the skill lives project-local at
`.claude/skills/assemble-ticket-context/`, the README is developer-facing, and
`installation-steps` (untracked) is the agent's setup checklist but has a
config-field bug (`token` vs the required `api_token`). The CLI itself is done
and its read-only guardrails already live in the code.

## Desired End State

A teammate clones the repo, pastes the README's top-of-file bootstrap prompt
into Claude Code, and the agent installs uv + the CLI, walks them through the
config, verifies with `auth-check`, then runs `uv run python install.py` — which
copies the skills to `~/.claude/skills/` and injects a brief `jira-tools` usage
block into `~/.claude/CLAUDE.md`. From then on the skill and the usage
instructions are available in every project.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Global memory path | `~/.claude/CLAUDE.md` (not `~/CLAUDE.md`) | Claude Code only reads user memory there; a bare `~/CLAUDE.md` is silently ignored | Research + Plan |
| Distribution home | `github.com/mlesniew/jira-tools` (personal repo) | Real and reachable today; nothing blocks shipping | Plan |
| Repo contents | Ship user-facing; keep `context/` dev docs; drop `lesson.md`/`vision` | Clean "how to use" surface without deleting project history | Plan |
| Uninstall | Install-only, no manifest | Vision never asks for uninstall; less code, fewer edge cases | Research + Plan |
| Tool scope | Claude Code only | Matches the vision exactly; simplest correct MVP | Research + Plan |
| Installer language/run | Python, `uv run python install.py` from the clone | uv+Python guaranteed present; `skills/` sits next to the script, outside `src/` | Research + Plan |
| Marker strings | `<!-- BEGIN jira-tools -->` / `<!-- END jira-tools -->` | Stable contract; Markdown comments are invisible when rendered | Research |
| Usage-block file | `rules/jira-tools.md` | Version-controlled body the script reads verbatim | Research |

## Scope

**In scope:** skill relocation to `skills/`; narration reword; `installation-steps`
fix + commit; `rules/jira-tools.md` usage block; idempotent `install.py`
(skill copy + sentinel injection) with a pytest suite; user-facing README with
bootstrap prompt.

**Out of scope:** package registry / `package.json` / CI publish / signing;
uninstall + manifest; multi-tool (Cursor/Codex) support; the script installing
uv or the config (those stay interactive with the agent); moving to an org repo;
stripping `context/foundation/` dev docs.

## Architecture / Approach

Two-world split inside one repo: source-of-truth artifacts (`skills/`,
`rules/jira-tools.md`) and the installer (`install.py`) coexist here; consumers
clone rather than pull from a registry. The dividing line is **interactive →
agent, mechanical → script**: the agent handles uv install, `uv tool install .`,
config creation, and `auth-check`; the script handles the idempotent file copies
and sentinel-marker injection.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Relocate & fix inputs | Skill in `skills/`, reworded narration, fixed+committed `installation-steps`, scratch files removed | Low — mostly `git mv` + text edits |
| 2. Usage block + `install.py` | Idempotent installer with full pytest coverage | The risk seam — sentinel edge cases (both/neither/one-corrupted), idempotency |
| 3. README + bootstrap prompt | User-facing README led by a copy-paste prompt | Prose quality; getting the prompt to reliably drive setup |

**Prerequisites:** none out-of-band — the GitHub remote already exists.
**Estimated effort:** ~1–2 sessions across 3 phases; Phase 2 carries most of it.

## Open Risks & Assumptions

- **Deviation from the vision text:** the vision says `~/CLAUDE.md`; we target
  `~/.claude/CLAUDE.md` because that is the only path Claude Code reads. This was
  confirmed with the user during planning.
- The clone home is a *personal* repo; if "for the team" later means an org
  namespace, the README + bootstrap prompt need a one-line URL update.
- Claude-Code-only is a deliberate MVP scope; Cursor/Codex would need a
  tool-profile refactor of the installer later.

## Success Criteria (Summary)

- A teammate can go from `git clone` → paste prompt → working skill + global
  usage block without hand-holding.
- `uv run python install.py` is idempotent and refuses to mangle a corrupted
  marker block.
- `uv run pytest`, `uv run mypy`, `uv run ruff check .` all pass.
