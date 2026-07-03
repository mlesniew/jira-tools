---
date: 2026-07-03T10:00:00+02:00
researcher: Michał Leśniewski
git_commit: 80fcbafd16b9cdd308445b56c063c6aac873ff6c
branch: master
repository: jira-tools
topic: "How to turn jira-tools into a shareable AI tool registry for the team (shared-ai-registry)"
tags: [research, codebase, distribution, skills, claude-md, installer]
status: complete
last_updated: 2026-07-03
last_updated_by: Michał Leśniewski
---

# Research: Turning jira-tools into a shareable AI tool registry

**Date**: 2026-07-03T10:00:00+02:00
**Researcher**: Michał Leśniewski
**Git Commit**: 80fcbafd16b9cdd308445b56c063c6aac873ff6c
**Branch**: master
**Repository**: jira-tools

## Research Question

How should we best implement the `shared-ai-registry` change described in
`vision`? The repo should become the team's shared AI package: it holds the
`jira-tools` CLI plus the skills that use it, ships a user-facing README with a
copy-paste bootstrap prompt, installs uv + the CLI via the agent, and uses a
deterministic script to install skills globally and inject `jira-tools`
usage instructions into the user's global Claude memory via the sentinel-marker
trick. `lesson.md` and `installation-steps` are the supporting inputs.

## Summary

The vision maps cleanly onto the lesson's **"Repository as the Source of
Truth"** pattern, but deliberately drops the registry/package-manager layer
("not building an NPM or PIP package… a simplified approach… acceptable"). The
right shape is therefore:

- **Distribution channel**: `git clone` (no registry). The repo *is* the
  package.
- **Split of responsibilities** (from the vision):
  - *Agent, directly & interactively*: install uv, `uv tool install .` to put
    `jira-tools` on `PATH`, walk the user through creating the config file, and
    run `auth-check`. This is inherently interactive (asks for site URL, email,
    token), so it fits the agent, not a script.
  - *Deterministic script*: copy `skills/*` → `~/.claude/skills/`, and inject
    the usage block into the global user memory file between sentinel markers.
    These are mechanical, idempotent, and must be repeatable — exactly what a
    script is for.
- **Portable patterns to keep from the lesson**: sentinel-marker injection
  (with the corrupted-block guard), idempotency, and `SKILL.md` as a
  tool-neutral file. **Patterns to explicitly reject**: registries, `package.json`,
  `.npmrc`, CI publish pipelines, semantic-release, signing — all Model 1/2/3
  machinery the vision rules out.

**Three findings materially shape the implementation and must not be missed:**

1. 🔴 **The global-memory path in the vision is wrong.** The vision says inject
   into `~/CLAUDE.md`. Claude Code reads global user memory from
   **`~/.claude/CLAUDE.md`**, not `~/CLAUDE.md`. Writing to `~/CLAUDE.md`
   directly in `$HOME` is **silently ignored**, so the whole injection feature
   would be inert. The script must target `~/.claude/CLAUDE.md`.
2. 🟠 **`installation-steps` names the config field `token`; the CLI requires
   `api_token`** (`src/jira_tools/config.py:12`). The README/bootstrap prompt
   must use `api_token` (the current README already does). Fix or annotate
   `installation-steps` so the two don't drift.
3. 🟠 **The skill must move `.claude/skills/ → skills/` and its "this repo's
   jira-tools CLI" wording must be audited.** Once installed globally and run
   from arbitrary consumer projects, "this repo" is misleading — but the bare
   `jira-tools <cmd>` invocations are already correct for a global
   `uv tool install`.

## Detailed Findings

### The distribution model (what the vision actually asks for)

The lesson (`lesson.md`) frames three distribution models around a package
*registry* (GitHub Packages / CodeArtifact / API+CLI) with an *installer* that
runs on the consumer side. The vision deliberately collapses this: there is no
registry and no package manager; the "single source of truth repo" and the
"installer" both live in *this* repo, and consumers get the artifacts by
cloning + running the bootstrap prompt.

This is legitimate under the lesson's own guidance ("choose what requires the
least effort while meeting the needs"; the "most common mistake" section warns
against distribution-for-the-CV). The recipient here is a small team that can
clone a repo; a registry would be over-engineering.

What we *do* carry over from the lesson's "Patterns That Will Survive Any
Model" (lesson.md:252–312):
- **Sentinel markers** for injecting into a human-edited rules file
  (lesson.md:256–287), including the corrupted-block case where only one marker
  survives manual editing (lesson.md:287).
- **Idempotency** — run twice, same result (lesson.md:165).
- **`SKILL.md` as a portable standard** (lesson.md:310) — the skill file is
  tool-neutral; only the target directory (`~/.claude/skills/`) is Claude-Code
  specific.

An **installation manifest** (lesson.md:289–308) is *optional* here: it only
earns its keep if we want clean uninstall. The vision doesn't mention
uninstall, so treat the manifest as a nice-to-have, not MVP.

### 🔴 Global memory path: `~/.claude/CLAUDE.md`, not `~/CLAUDE.md`

Verified against Claude Code's official docs (via the claude-code-guide agent,
citing https://code.claude.com/docs/llms.txt): global user-level memory is read
from **`~/.claude/CLAUDE.md`**. A file at `~/CLAUDE.md` (bare in `$HOME`) is not
part of the documented memory hierarchy and is **silently ignored** for the
global-instructions purpose.

Implication for the script:
- Inject the `jira-tools` usage block into `~/.claude/CLAUDE.md`.
- The file frequently **does not exist yet** (it did not exist on this machine
  at research time). The script must create it (and `~/.claude/` should already
  exist because skills install there) rather than assuming it's present.
- Note the naming collision to avoid confusion: this repo already has its own
  project-level `CLAUDE.md` at the repo root (project memory). The injection
  target is the *user-global* one under `~/.claude/`, a different file.

### The "usage instructions" file to inject

The vision wants "a file … [with] brief instructions on how to use
`jira-tools`" that gets injected into global memory. Design points:

- Keep it **brief and action-oriented** — global memory is always-loaded
  context, so it should be a few lines: what `jira-tools` is, the key
  subcommands, and that the `assemble-ticket-context` skill exists. Not a
  copy of the README.
- Store it as a standalone file in the repo (e.g. `rules/jira-tools.md` or
  `global-claude-md-block.md`) so it's version-controlled and the script reads
  it verbatim as the marker-block body. This mirrors the lesson's
  `rules/CLAUDE.md` artifact (lesson.md:71–72, 462–463).
- Content should reflect the **installed** invocation (`jira-tools fetch-ticket
  …`), not `uv run jira-tools …`, because the global tool is on `PATH`.

The actual CLI surface to document (from `src/jira_tools/cli.py`):
- `jira-tools version` (`cli.py:30`)
- `jira-tools auth-check` (`cli.py:38`)
- `jira-tools fetch-ticket <KEY>` (`cli.py:57`)
- `jira-tools fetch-page <ID>` (`cli.py:78`)
- `jira-tools extract-links <KEY>` (`cli.py:105`)

### Sentinel-marker injection algorithm

Follow the lesson's algorithm (lesson.md:269–287), adapted to Markdown comment
markers so they're invisible when the file renders:

```
<!-- BEGIN jira-tools -->
… usage block …
<!-- END jira-tools -->
```

Behavior the script must implement:
- **Both markers present** → replace only the text between them; leave
  everything else (the user's own notes) untouched.
- **Neither present** → append the block (after a blank line) to the end; create
  the file if missing.
- **Exactly one marker present (corrupted block)** → do *not* blindly append, or
  you duplicate/mangle rules. The lesson explicitly calls this out
  (lesson.md:287) as a case "that must be handled separately." Safest MVP
  behavior: refuse and tell the user to fix the file manually, rather than
  guess.
- Choose a **stable marker string** and never change it across versions, or old
  blocks orphan.

### Skill relocation: `.claude/skills/` → `skills/`

Current state: the sole skill lives at
`.claude/skills/assemble-ticket-context/SKILL.md` (project-local, single file,
no `references/` subdir). The vision wants skills under `skills/` at the repo
root because they are meant to be *installed globally*, not used against this
repo.

Required moves/edits:
- `git mv .claude/skills/assemble-ticket-context skills/assemble-ticket-context`.
- Audit the SKILL.md wording. Line 21–24 says it "only ever calls the existing
  `jira-tools` CLI … using **this repo's** jira-tools CLI." Once the skill is
  installed into `~/.claude/skills` and invoked from an unrelated consumer
  project, "this repo's" is wrong. The **commands themselves are already
  correct** — the skill calls bare `jira-tools auth-check` / `fetch-ticket` /
  `extract-links` / `fetch-page` (SKILL.md:37, 58, 71, 132–133), which resolve
  via the global `uv tool install`. Only the *narration* needs to change to
  "the globally-installed `jira-tools` CLI."
- Decide whether the skill also stays available for local dogfooding. Simplest:
  `skills/` is the single source; the install script copies it to
  `~/.claude/skills/`. If you still want it active while developing *this* repo,
  the copy-to-global step covers that too (it's the same machine).

### The install script: language and shape

**Recommended language: Python**, run via the repo's own toolchain
(`uv run python install.py` or a `[project.scripts]`-style entry). Rationale:
- uv + Python are guaranteed present after the agent's install step, so there's
  no new runtime dependency (a Bash script would also work but is harder to keep
  idempotent and cross-shell-safe; the lesson's JS/TS installer is irrelevant
  here since we're not in npm).
- Matches the repo's stack and its `mypy --strict` / `ruff` conventions
  (`CLAUDE.md`), so the script is held to the same quality bar and is testable
  under `pytest`.

What the script does (all idempotent):
1. **Copy skills**: for each dir in `skills/`, copy to
   `~/.claude/skills/<name>/`. Idempotent = overwrite/replace target contents so
   re-running updates in place. (Copy, not symlink — the vision wants a global
   install independent of where the repo sits, and the user may move/delete the
   clone.)
2. **Inject usage block** into `~/.claude/CLAUDE.md` via the sentinel algorithm
   above (create file if missing; handle corrupted-block case).
3. Print a short summary of what it did (files written, marker updated/created).

Explicitly **out of scope for the script** (the agent handles these per the
vision, because they're interactive): installing uv, `uv tool install .`, and
creating/validating `~/.config/jira-tools/config.toml`.

### The README (user-facing) and the bootstrap prompt

The vision wants the README rewritten to be **user-consumable — how to *use* the
package, not how to develop it** — with (a) easy install instructions derived
from `installation-steps`, and (b) a **copy-paste prompt at the very top** that
the user drops into Claude after cloning.

Current `README.md` is developer-facing (`uv sync`, `uv run pytest`, mypy,
ruff). Recommended restructure:
1. **Top: the bootstrap prompt** — a fenced block the user copies into Claude,
   e.g. *"Set up jira-tools on my machine following installation-steps: install
   uv if needed, install the CLI, help me create the config, verify with
   auth-check, then run the install script to add the skills and global
   instructions."* The prompt should point the agent at `installation-steps`
   (the deterministic checklist already in the repo) so behavior is consistent.
2. **What it is** — one paragraph: read-only Jira/Confluence context assembler +
   the `assemble-ticket-context` skill.
3. **Manual install steps** — the human-readable version of `installation-steps`
   as a fallback, using the **correct `api_token` field**.
4. Move the current dev instructions to a short "Development" section or into
   the project `CLAUDE.md`.

The developer-facing PRD/dev notes should stop being the README's main content.

### 🟠 `installation-steps` accuracy fixes

`installation-steps` is the source of truth for the agent's interactive setup,
so its errors propagate. Fix before building on it:
- **Line 11: `token` → `api_token`.** The Pydantic model requires exactly
  `site_url`, `email`, `api_token` (`config.py:12,18–20`); a file with `token`
  fails validation with "missing or invalid field(s): api_token".
- Line 6/9 uses `~/.config/jira-tools/config.toml`. The CLI is XDG-aware:
  `$XDG_CONFIG_HOME/jira-tools/config.toml`, falling back to `~/.config/...`
  only when `XDG_CONFIG_HOME` is unset (`config.py:42–44`). Fine to keep the
  `~/.config` phrasing for humans, but know it's a fallback.
- Step 4 ("Install the skill files from `skills/` to `~/.claude/skills`") is the
  step the deterministic script implements — good, already aligned with the
  vision. Note it currently points at `skills/`, which doesn't exist yet until
  the relocation happens.
- `auth-check` exits non-zero and prints `PASS`/`FAIL` per product
  (`cli.py:38–53`); the config loader never echoes the token
  (`config.py:48–72`), and `auth-check` warns (without failing) if the config
  file is group/other-readable (`config.py:75–79`, `cli.py:42`). The
  guardrails the PRD promises are already enforced in code.

## Code References

- `src/jira_tools/cli.py:30` — `version` command (so `jira-tools version`
  works as the post-install smoke test in `installation-steps` step 2).
- `src/jira_tools/cli.py:38-53` — `auth-check`: per-product PASS/FAIL, non-zero
  exit on failure, permission warning, no token echo.
- `src/jira_tools/cli.py:57,78,105` — `fetch-ticket`, `fetch-page`,
  `extract-links` — the CLI surface the skill and the usage block document.
- `src/jira_tools/config.py:12` — `REQUIRED_FIELDS = ("site_url", "email",
  "api_token")` — the authoritative field names (contradicts
  `installation-steps` line 11).
- `src/jira_tools/config.py:42-44` — XDG-aware config path resolution.
- `.claude/skills/assemble-ticket-context/SKILL.md:21-24` — "this repo's
  jira-tools CLI" wording to audit on relocation.
- `pyproject.toml` `[project.scripts] jira-tools = "jira_tools:main"` — the
  entry point that `uv tool install .` exposes on `PATH`.
- `README.md` — currently developer-facing; to be rewritten user-facing.
- `installation-steps` — the agent's interactive setup checklist (fix `token`).

## Architecture Insights

- **Two-world split, one repo.** Source-of-truth artifacts (`skills/`, the
  usage-block file) and the installer (`install.py`) coexist here; consumers
  clone rather than pull from a registry. This is the lesson's core pattern with
  the registry removed.
- **Interactive vs. deterministic boundary.** The clean line is: anything that
  asks the user something (uv install choice, credentials) → agent; anything
  mechanical and repeatable (file copies, marker injection) → script. This is
  exactly the vision's split and keeps the script pure/idempotent/testable.
- **Idempotency is the correctness property.** All three script writes (skill
  copy, config already-exists, sentinel block already-present) must be safe to
  re-run. The config case is already handled by the agent side
  (`installation-steps` 3a pauses if the file exists).
- **Guardrails already live in the CLI layer** (read-only clients, no token in
  output, graceful config errors), so the skill/script layer doesn't need to
  re-implement safety — it just needs to not *undo* it (e.g. don't dump config
  contents in logs).

## Historical Context (from prior changes)

- `context/changes/assemble-ticket-context/` (recent commits `73a2ed1`,
  `c26efef`, `5d114f8`, `ff2f37f`, `80fcbaf`) — built the skill that this
  change now packages for distribution. The frontmatter/auth pre-flight and
  read-only-at-the-tool-level design there (Explore subagents) are why the
  skill is already safe to hand to other users.
- `context/foundation/prd.md`, `roadmap.md`, `shape-notes.md`,
  `tech-stack.md` — foundation for the CLI itself; the PRD's read-only /
  no-credentials-in-output guardrails are the constraints the distribution
  layer must preserve.
- No `context/foundation/lessons.md` exists yet — no accepted team-wide rules to
  reconcile against for this change.

## Related Research

None prior for this change; this is the first research artifact under
`context/changes/shared-ai-registry/`.

## Open Questions

1. **Uninstall in scope?** If yes, add the lesson's manifest pattern
   (`~/.claude/.jira-tools-manifest.json`) so removal is exact rather than
   guessed. If no (recommended for MVP), skip it.
2. **Where the team clones from.** This repo currently has **no GitHub remote**
   (`gh repo view` → no remote). The bootstrap prompt/README assume a clone
   exists; the team needs a hosting location (GitHub/GitLab/internal) decided
   before the README's "clone this repo" line is real.
3. **Exact usage-block file location/name** (`rules/jira-tools.md` vs. a
   top-level file) and the exact marker string — cosmetic but must be locked
   before the script hard-codes them.
4. **Multi-tool ambition.** The lesson stresses tool-neutral `SKILL.md`. The
   vision only asks for Claude Code (`~/.claude/skills`, `~/.claude/CLAUDE.md`).
   Keeping the script Claude-Code-only is fine for MVP; note it as a known
   single-tool scope if Cursor/Codex support is ever wanted.
