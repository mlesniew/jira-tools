# Shared AI Tool Registry Implementation Plan

## Overview

Turn `jira-tools` into the team's shared AI tool registry: the repo *is* the
package (no npm/PyPI registry), distributed by `git clone` + a copy-paste
bootstrap prompt. The bootstrap prompt drives the agent through the interactive
setup (install uv, `uv tool install .`, create the config, `auth-check`), then
the agent runs a deterministic Python installer that copies the skills to
`~/.claude/skills/` and injects a brief `jira-tools` usage block into the user's
global Claude memory (`~/.claude/CLAUDE.md`) via the sentinel-marker trick.

## Current State Analysis

- The sole skill lives at `.claude/skills/assemble-ticket-context/SKILL.md`
  (project-local, single file, no `references/` subdir). Its `description`
  frontmatter says it uses "**this repo's** jira-tools CLI" (`SKILL.md:3`) —
  misleading once installed globally and run from arbitrary consumer projects
  (the body prose at `SKILL.md:21–22` says "the existing `jira-tools` CLI",
  which is neutral but can be reworded to "globally-installed" for clarity). The
  bare command
  invocations (`jira-tools auth-check` / `fetch-ticket` / `extract-links` /
  `fetch-page`, `SKILL.md:37,58,71,132–133`) are already correct for a global
  `uv tool install`.
- `README.md` is developer-facing (`uv sync`, `uv run pytest`, mypy, ruff).
- `installation-steps` (untracked, `??`) is the agent's interactive setup
  checklist. It names the config field `token` (line 11) but the CLI requires
  `api_token` (`src/jira_tools/config.py:12`
  `REQUIRED_FIELDS = ("site_url", "email", "api_token")`). It references
  `skills/`, which does not exist yet.
- `pyproject.toml` exposes the console entry `jira-tools = "jira_tools:main"`
  (`[project.scripts]`), which `uv tool install .` puts on `PATH`.
- The CLI surface to document lives in `src/jira_tools/cli.py`: `version`
  (`cli.py:30`), `auth-check` (`cli.py:38`), `fetch-ticket` (`cli.py:57`),
  `fetch-page` (`cli.py:78`), `extract-links` (`cli.py:105`).
- The repo now has a GitHub remote — `git@github.com:mlesniew/jira-tools.git`
  (research Open-Q#2 is resolved; the clone home is
  `github.com/mlesniew/jira-tools`).
- `lesson.md` (48KB course material) and `vision` (personal scratch) are
  untracked and dev-only — they should not ship to teammates.
- No `context/foundation/lessons.md` exists — no accepted team rules to
  reconcile against.

## Desired End State

A teammate can:

1. `git clone git@github.com:mlesniew/jira-tools.git && cd jira-tools`.
2. Paste the README's top-of-file bootstrap prompt into Claude Code.
3. The agent installs uv (if needed), runs `uv tool install .`, walks them
   through `~/.config/jira-tools/config.toml` (fields `site_url`, `email`,
   `api_token`), and verifies with `jira-tools auth-check`.
4. The agent runs `uv run python install.py`, which copies `skills/*` into
   `~/.claude/skills/` and injects a brief usage block into
   `~/.claude/CLAUDE.md` between `<!-- BEGIN jira-tools -->` /
   `<!-- END jira-tools -->` markers.
5. From then on, in any project, the `assemble-ticket-context` skill is
   available and the global memory tells Claude what `jira-tools` is and how to
   call it.

Verification: `uv run python install.py` is idempotent (run twice → identical
result); the skill directory and marker block appear under `~/.claude/`;
`uv run pytest`, `uv run mypy`, `uv run ruff check .` all pass.

### Key Discoveries:

- 🔴 Global memory path is `~/.claude/CLAUDE.md`, **not** `~/CLAUDE.md`
  (research.md:103–118). A bare `~/CLAUDE.md` is silently ignored, so the
  vision's literal path would make the injection inert. Confirmed decision:
  target `~/.claude/CLAUDE.md`, create if missing. (Deviation from the vision
  text — see Open Risks.)
- 🟠 `installation-steps:11` says `token`; the CLI requires `api_token`
  (`config.py:12`). Must fix before the file ships.
- 🟠 `SKILL.md:3` (`description` frontmatter) "this repo's jira-tools CLI"
  narration must become "globally-installed"; the body prose at `SKILL.md:21–22`
  ("the existing `jira-tools` CLI") may be reworded to match. The commands
  themselves stay unchanged.
- `install.py` must be run as `uv run python install.py` **from the clone** —
  `skills/` sits at repo root, *outside* `src/jira_tools/`, so it is not
  packaged by `uv tool install .` and a console-script entry could not locate it
  from an arbitrary CWD (research Architecture Insights; verified via
  `pyproject.toml` layout).
- Sentinel algorithm (lesson.md:269–287): both markers → replace between; neither
  → append (create file if missing); exactly one → refuse (corrupted block,
  lesson.md:287).

## What We're NOT Doing

- No package registry, `package.json`, `.npmrc`, CI publish pipeline,
  semantic-release, or signing (Model 1/2/3 machinery the vision rules out).
- No uninstall / installation manifest (`~/.claude/.jira-tools-manifest.json`) —
  install-only MVP.
- No multi-tool support (Cursor/Codex). Claude Code only; `~/.claude/skills` and
  `~/.claude/CLAUDE.md` are hard-coded. `SKILL.md` stays tool-neutral so
  generalization is possible later.
- The script does **not** install uv, run `uv tool install .`, or create/validate
  the config — those are interactive and stay with the agent per
  `installation-steps`.
- Not moving the repo to an org; the personal `mlesniew/jira-tools` remote is the
  distribution home for now.
- Not stripping `context/foundation/` dev docs — they stay in-repo, just out of
  the README's spotlight.

## Implementation Approach

Two-world split inside one repo: source-of-truth artifacts (`skills/`,
`rules/jira-tools.md`) and the installer (`install.py`) coexist here; consumers
clone rather than pull from a registry. The clean boundary is
**interactive → agent, mechanical → script**. Build in three phases, front-to-back
by risk: relocate the skill and fix the source-of-truth inputs first (cheap,
unblocks everything), then the installer + its test suite (the risk seam), then
the user-facing README that ties it together.

## Critical Implementation Details

**Sentinel injection is the load-bearing, error-prone part.** Three marker
states must each be handled (both present → replace between; neither → append
after a blank line, creating the file if missing; exactly one → refuse and tell
the user to fix the file by hand rather than guess). The marker strings
(`<!-- BEGIN jira-tools -->` / `<!-- END jira-tools -->`) are a stable contract —
never change them across versions or old blocks orphan. `~/.claude/CLAUDE.md`
frequently does not exist yet; `~/.claude/` will exist because skills install
there, but the script must still create the file (and parent dir) defensively.

## Phase 1: Relocate skill & fix source-of-truth inputs

### Overview

Move the skill to its distribution home, correct the narration that only made
sense in-repo, fix the config-field drift in `installation-steps`, commit that
file so the bootstrap prompt can reference it, and drop the personal/course
scratch files so they don't ship to teammates.

### Changes Required:

#### 1. Relocate the skill

**File**: `.claude/skills/assemble-ticket-context/` → `skills/assemble-ticket-context/`

**Intent**: `skills/` at repo root is the single source of truth for globally
installed skills. Preserve git history for the move.

**Contract**: `git mv .claude/skills/assemble-ticket-context skills/assemble-ticket-context`.
The `.claude/skills/` directory is left empty/removed. `skills/` is the sole
copy — the skill is no longer active against *this* repo except via the global
install (same machine).

#### 2. Reword skill narration for global use

**File**: `skills/assemble-ticket-context/SKILL.md`

**Intent**: Once installed into `~/.claude/skills` and invoked from an unrelated
project, "this repo's jira-tools CLI" is wrong. Reword the narration to name the
globally-installed CLI; leave every command invocation untouched.

**Contract**: Edit the `description` frontmatter (`SKILL.md:3`, which says "this
repo's jira-tools CLI") to read "the globally-installed `jira-tools` CLI"; also
reword the body prose at `SKILL.md:21–22` ("the existing `jira-tools` CLI") to
match. No change to `auth-check` / `fetch-ticket` / `extract-links` /
`fetch-page` invocations.

#### 3. Fix and commit `installation-steps`

**File**: `installation-steps`

**Intent**: This is the agent's interactive checklist and the bootstrap prompt
references it by name — it must be correct and tracked in git.

**Contract**: Change the config field `token` → `api_token` (line 11) — this is
the field name the CLI's config.toml actually requires (`config.py:12`), so the
checklist must instruct the user to create an `api_token` entry, not `token`.
Rewrite step 4 from a *manual* skill copy ("Install the skill files from skills/
to ~/.claude/skills") to **"run `uv run python install.py` from the clone"** — so
the single mechanical installer owns skill copy *and* memory-block injection, and
the interactive→agent / mechanical→script split holds. (The manual copy at step 4
would otherwise skip the memory injection that lives only in `install.py`,
yielding an incomplete setup that drops Desired End State points 4–5.) Optionally
note the config path is XDG-aware (`$XDG_CONFIG_HOME/jira-tools/config.toml`,
falling back to `~/.config/...`). `git add installation-steps` so it ships.

Because `install.py` is idempotent, the bootstrap prompt's own
"then run `uv run python install.py`" (Phase 3) and this step 4 may both fire in
one session — that is a harmless no-op, not two live install paths.

#### 4. Drop personal/course scratch files

**File**: `lesson.md`, `vision`

**Intent**: 48KB of course material and a personal vision note should not ship in
a package teammates clone.

**Contract**: `git rm`/delete `lesson.md` and `vision` (both currently
untracked, so a filesystem delete suffices). `context/foundation/` and other dev
docs stay in-repo. `installation-steps` is the exception — it ships (change #3).

### Success Criteria:

#### Automated Verification:

- Skill exists at new path: `test -f skills/assemble-ticket-context/SKILL.md`
- Old skill path is gone: `test ! -d .claude/skills/assemble-ticket-context`
- No stale "this repo's" narration: `! grep -rn "this repo's jira-tools" skills/`
- `installation-steps` names the config field `api_token`, and no bullet still uses a bare `token` field: `grep -q "api_token" installation-steps && ! grep -qE '^\s*\*\s*token\b' installation-steps` (the negative check is scoped to the config-field bullet — plain prose like "an access token" must not trip it)
- Type/lint/tests still pass: `uv run mypy`, `uv run ruff check .`, `uv run pytest`

#### Manual Verification:

- The `assemble-ticket-context` skill still loads and runs against a real ticket
  from an arbitrary directory (dogfood via the global install).
- `installation-steps` reads correctly end-to-end as an agent checklist.
- `lesson.md` / `vision` no longer present in the working tree.

**Implementation Note**: After completing this phase and all automated
verification passes, pause for manual confirmation before proceeding.

---

## Phase 2: Usage block + `install.py` with tests

### Overview

Author the brief global-memory usage block, then write the idempotent Python
installer that copies skills into `~/.claude/skills/` and injects the block into
`~/.claude/CLAUDE.md` via the sentinel algorithm — with a pytest suite covering
every marker state, idempotency, and file/dir creation. This is the risk seam;
its success criteria are real automated checks.

### Changes Required:

#### 1. The usage-block artifact

**File**: `rules/jira-tools.md`

**Intent**: A brief, action-oriented block injected into always-loaded global
memory — what `jira-tools` is, its key subcommands, and that the
`assemble-ticket-context` skill exists. Not a copy of the README. The script
reads this file verbatim as the marker-block body.

**Contract**: A few lines of Markdown reflecting the **installed** invocation
(`jira-tools fetch-ticket <KEY>`, not `uv run jira-tools …`). Documents the CLI
surface: `version`, `auth-check`, `fetch-ticket <KEY>`, `fetch-page <ID>`,
`extract-links <KEY>`, and a one-liner that the `assemble-ticket-context` skill
assembles one-hop ticket context. The file body must **not** itself contain the
sentinel marker strings (guard against self-injection).

#### 2. Sentinel injection function

**File**: `install.py`

**Intent**: Idempotently inject `rules/jira-tools.md`'s content into a target
memory file between stable markers, correctly handling all three marker states.

**Contract**: A pure function taking `(existing_text: str, block_body: str) ->
str` (or raising on the corrupted case) so it is unit-testable without touching
the real `~/.claude/CLAUDE.md`. Marker constants
`BEGIN = "<!-- BEGIN jira-tools -->"`, `END = "<!-- END jira-tools -->"`.
Behavior:
- **Both markers present** → replace only the text between them, preserve the
  rest verbatim.
- **Neither present** → append `\n\n{BEGIN}\n{body}\n{END}\n` after the existing
  content (trimmed of trailing whitespace); if the file is missing, treat
  existing as empty and create it.
- **Exactly one present** → raise / return an error signal; the caller prints a
  clear message telling the user to fix the file by hand and does **not** write.
Fully typed for `mypy --strict`.

#### 3. Skill-copy + orchestration

**File**: `install.py`

**Intent**: Copy each `skills/<name>/` into `~/.claude/skills/<name>/`,
mirroring the source (remove the target skill dir first, then copy) so a file
deleted upstream doesn't linger in `~/.claude/skills/`, then call the injection
function against
`~/.claude/CLAUDE.md` (creating `~/.claude/` and the file if absent), then print
a short summary of what was written.

**Contract**: Resolve source `skills/` relative to the script's own location
(`__file__`), not CWD, so it works regardless of where the agent runs it from.
Copy (not symlink) — the user may move/delete the clone. Target paths derived
from `Path.home() / ".claude"`. Idempotent: each target skill dir is
removed then re-copied so the target mirrors the source (no stale files);
injection is idempotent by construction. On the corrupted-block
case, exit non-zero with the fix-by-hand message. Never print config/secret
contents (the script never reads config, but keep output limited to file paths
and marker status).

#### 4. Installer test suite

**File**: `tests/test_install.py`

**Intent**: Lock the installer's correctness — especially the three marker
states and idempotency — before anyone relies on it.

**Contract**: Use `tmp_path` / monkeypatched `Path.home()` so tests never touch
the real `~/.claude/`. Cases:
- Both markers present → block between them replaced, surrounding text intact.
- Neither present → block appended; run again → identical output (idempotency).
- Exactly one marker → refuses (raises / non-zero) and leaves the file
  unchanged.
- `~/.claude/CLAUDE.md` missing → file (and `~/.claude/` if needed) created with
  the block.
- Skill copy → `skills/*` land under the fake home's `~/.claude/skills/`; second
  run produces the same tree (idempotent). A stale file pre-seeded in the target
  skill dir is gone after a run (source-mirroring, not merge).
- Guardrail → installer output contains no config/secret material (only paths /
  marker status).

### Success Criteria:

#### Automated Verification:

- Installer tests pass: `uv run pytest tests/test_install.py`
- Full suite passes: `uv run pytest`
- Type checking passes: `uv run mypy`
- Linting passes: `uv run ruff check .`
- Idempotency asserted in tests (run-twice-same-result for both injection and
  skill copy).
- `rules/jira-tools.md` contains no sentinel markers:
  `! grep -q "BEGIN jira-tools" rules/jira-tools.md`

#### Manual Verification:

- `uv run python install.py` on a real machine copies the skill to
  `~/.claude/skills/assemble-ticket-context/` and injects the block into
  `~/.claude/CLAUDE.md`.
- Running it a second time changes nothing (diff the file / dir before & after).
- Manually corrupting the block (delete one marker) → the next run refuses with a
  clear fix-by-hand message and doesn't mangle the file.
- Hand-edited notes outside the markers survive a re-run.

**Implementation Note**: After completing this phase and all automated
verification passes, pause for manual confirmation before proceeding.

---

## Phase 3: User-facing README + bootstrap prompt

### Overview

Rewrite the README so it reads as *how to use this package*, led by a copy-paste
bootstrap prompt, with the current developer instructions demoted to a short
Development section.

### Changes Required:

#### 1. Rewrite `README.md`

**File**: `README.md`

**Intent**: Make the README user-consumable and give the teammate a single
prompt to paste into Claude after cloning.

**Contract**: Top-down structure:
1. **Bootstrap prompt** — a fenced block the user copies into Claude Code,
   pointing the agent at `installation-steps` (the deterministic checklist) and
   ending with "then run `uv run python install.py` to install the skills and
   global instructions". Phrased so the agent: installs uv if needed, runs
   `uv tool install .`, helps create the config, verifies with `auth-check`,
   then runs the installer.
2. **What it is** — one paragraph: read-only Jira/Confluence one-hop context
   assembler + the `assemble-ticket-context` skill.
3. **Manual install** — the human-readable version of `installation-steps`,
   using the correct `api_token` field, including the `git clone
   git@github.com:mlesniew/jira-tools.git` line.
4. **Development** — a short section retaining `uv sync` / `uv run pytest` /
   `mypy` / `ruff` for contributors.

The clone URL is hard-coded to `git@github.com:mlesniew/jira-tools.git`.

### Success Criteria:

#### Automated Verification:

- README references the installer and correct field:
  `grep -q "install.py" README.md && grep -q "api_token" README.md`
- README hard-codes the clone URL:
  `grep -q "mlesniew/jira-tools" README.md`
- No stale `token`-only config example: `! grep -qxE "\s*token\s*=.*" README.md`

#### Manual Verification:

- A teammate unfamiliar with the repo can follow the README top-to-bottom:
  clone → paste bootstrap prompt → agent completes setup → skill works.
- The bootstrap prompt, pasted into Claude, drives the full interactive setup
  without the human needing to read `installation-steps` themselves.
- Dev instructions are still discoverable for contributors.

**Implementation Note**: After completing this phase and all automated
verification passes, pause for final manual confirmation.

---

## Testing Strategy

### Unit Tests:

- Sentinel injection: all three marker states (both / neither / one-corrupted).
- Idempotency: injection and skill copy both run-twice-same-result.
- File/dir creation when `~/.claude/CLAUDE.md` is missing.
- Guardrail: installer output carries no config/secret material.

### Integration Tests:

- End-to-end `install.py` run against a fake home (`tmp_path` + monkeypatched
  `Path.home()`): skill dir + marker block both materialize; second run is a
  no-op diff.

### Manual Testing Steps:

1. Fresh-ish machine: clone, paste bootstrap prompt, confirm the agent completes
   uv + `uv tool install .` + config + `auth-check`.
2. Confirm `uv run python install.py` creates
   `~/.claude/skills/assemble-ticket-context/` and injects the block into
   `~/.claude/CLAUDE.md`.
3. Add a personal note outside the markers, re-run the installer, confirm the
   note survives and the block updates.
4. Delete one marker, re-run, confirm refusal + no mangling.
5. From an unrelated project, invoke `assemble-ticket-context` and confirm it
   runs via the global `jira-tools`.

## Performance Considerations

None material — the installer touches a handful of small files. Idempotency, not
speed, is the correctness property.

## Migration Notes

Existing local users of the in-repo `.claude/skills/` skill: after the move, the
skill is delivered via the global install instead. Running `install.py` on the
same dev machine covers dogfooding. No data migration.

## References

- Related research: `context/changes/shared-ai-registry/research.md`
- Vision (dev-only, to be removed in Phase 1): `vision`
- Lesson source (dev-only, to be removed in Phase 1): `lesson.md`
- Sentinel algorithm: `lesson.md:269–287` (both/neither/one-corrupted at :287)
- Config field authority: `src/jira_tools/config.py:12`
- CLI surface: `src/jira_tools/cli.py:30,38,57,78,105`
- Skill narration to reword: `skills/assemble-ticket-context/SKILL.md:3` (frontmatter), `:21–22` (body)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles. See `references/progress-format.md`.

### Phase 1: Relocate skill & fix source-of-truth inputs

#### Automated

- [x] 1.1 Skill exists at new path: `test -f skills/assemble-ticket-context/SKILL.md`
- [x] 1.2 Old skill path is gone: `test ! -d .claude/skills/assemble-ticket-context`
- [x] 1.3 No stale "this repo's" narration: `! grep -rn "this repo's jira-tools" skills/`
- [x] 1.4 `installation-steps` names the config field `api_token`, no bullet uses bare `token`: `grep -q "api_token" installation-steps && ! grep -qE '^\s*\*\s*token\b' installation-steps`
- [x] 1.5 Type/lint/tests still pass: `uv run mypy`, `uv run ruff check .`, `uv run pytest`

#### Manual

- [ ] 1.6 Skill loads and runs from an arbitrary directory via the global install
- [ ] 1.7 `installation-steps` reads correctly end-to-end as an agent checklist
- [ ] 1.8 `lesson.md` / `vision` no longer present in the working tree

### Phase 2: Usage block + `install.py` with tests

#### Automated

- [ ] 2.1 Installer tests pass: `uv run pytest tests/test_install.py`
- [ ] 2.2 Full suite passes: `uv run pytest`
- [ ] 2.3 Type checking passes: `uv run mypy`
- [ ] 2.4 Linting passes: `uv run ruff check .`
- [ ] 2.5 Idempotency asserted in tests (injection + skill copy)
- [ ] 2.6 `rules/jira-tools.md` contains no sentinel markers

#### Manual

- [ ] 2.7 `uv run python install.py` copies skill + injects block on a real machine
- [ ] 2.8 Second run changes nothing (idempotent)
- [ ] 2.9 Corrupted block (one marker) → refusal + no mangling
- [ ] 2.10 Hand-edited notes outside the markers survive a re-run

### Phase 3: User-facing README + bootstrap prompt

#### Automated

- [ ] 3.1 README references `install.py` and `api_token`
- [ ] 3.2 README hard-codes the `mlesniew/jira-tools` clone URL
- [ ] 3.3 No stale `token`-only config example in README

#### Manual

- [ ] 3.4 A teammate can follow the README top-to-bottom to a working setup
- [ ] 3.5 The bootstrap prompt drives full interactive setup without reading `installation-steps`
- [ ] 3.6 Dev instructions still discoverable for contributors
