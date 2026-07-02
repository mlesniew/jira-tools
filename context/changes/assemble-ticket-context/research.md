---
date: 2026-07-02T15:04:29+02:00
researcher: Michał Leśniewski
git_commit: d942db951daeb3bf89fdc4bce94a77fc75f00d43
branch: master
repository: jira-tools
topic: "Polish the assemble-ticket-context skill for standalone, end-to-end, developer-useful runs"
tags: [research, codebase, assemble-ticket-context, skill, jira-tools-cli]
status: complete
last_updated: 2026-07-02
last_updated_by: Michał Leśniewski
last_updated_note: "Scoped out standalone-invocation fix per user decision; auth-check pre-flight is now the sole standalone-ness gate"
---

# Research: Polish the assemble-ticket-context skill

**Date**: 2026-07-02T15:04:29+02:00
**Researcher**: Michał Leśniewski
**Git Commit**: d942db951daeb3bf89fdc4bce94a77fc75f00d43
**Branch**: master
**Repository**: jira-tools

## Research Question

`context/changes/assemble-ticket-context/change.md` asks to polish the
`assemble-ticket-context` skill (`.claude/skills/assemble-ticket-context/SKILL.md`)
so it: (1) runs end-to-end standalone in Claude without relying on
`CLAUDE.md`, other files, or user-supplied context; (2) checks that
`jira-tools` is configured and working (auth) before doing anything else,
stopping cleanly if not; and (3) is generally more useful for developers.
Scoped by the user to two research angles: **skill content/UX quality**
against the PRD, and **Claude Code skill conventions** used elsewhere in this
environment.

## Summary

The skill is structurally sound against the PRD (all of FR-005–FR-008
covered, no Non-Goal violations) but has one **blocking self-containment
bug** and a handful of real (non-blocking) quality gaps:

1. ~~**Bare `jira-tools` won't run standalone.**~~ **Out of scope per user
   decision (2026-07-02)**: the user has decided to assume `jira-tools` is
   installed/on `PATH` wherever the skill runs, so SKILL.md's bare
   `jira-tools fetch-ticket <KEY>` / `extract-links` / `fetch-page` commands
   (lines 31, 45, 99–100) do not need a `uv run` prefix or working-directory
   fix. `auth-check` (Finding 2) is the intended substitute guardrail: if
   the binary genuinely isn't installed/configured, `auth-check` fails
   loudly at the start instead of the skill silently assuming success.
2. **No auth-check pre-flight (now the primary fix).** The CLI already ships a purpose-built
   `jira-tools auth-check` command (`src/jira_tools/cli.py:38-54`) that
   validates config presence/shape and both Jira/Confluence credentials
   without ever printing the token — exactly what the change asks for. It
   already exists; SKILL.md just never calls it before Step 1.
3. **Wrong subagent type for the dispatch step.** SKILL.md step 3 dispatches
   `Explore`-type subagents (SKILL.md:88–89), but every other skill in this
   environment defines `Explore` as fast file/pattern search, and pairs
   "run a command, then synthesize/condense from a given perspective" work
   with `general-purpose` instead. `Explore` is the wrong tool for "run
   this exact CLI command and condense its output," even though it does
   happen to satisfy the read-only guardrail structurally.
4. **Thin frontmatter.** Only `name` + `description` — no `allowed-tools`,
   despite the skill's read-only guarantee being a headline feature that
   almost every other skill in this repo/environment encodes structurally
   via `allowed-tools` rather than prose alone.
5. **Template/prompt fidelity gaps** (non-blocking polish): the per-item
   subagent prompt doesn't ask for a title separate from the "why it
   matters" sentence, but the report template needs a clean `<title>` slot;
   gap messages will always read as the CLI's one generic string
   ("not found or not accessible") regardless of actual cause, because
   `cli.py` collapses all failure modes into one message; `JiraTicket` never
   carries assignee/priority/sprint/due-date (an FR-001 CLI scope
   limitation, not fixable in SKILL.md alone, but worth flagging as a
   "meeting prep" gap).

No PRD/FR violations were found — the skill's design (one-hop only,
unfiltered dispatch, condensation-not-raw-dump, live-load-as-default with
save-as-follow-up) already matches FR-005–FR-008 and the Non-Goals
correctly.

## Detailed Findings

### 1. Standalone invocation — out of scope per user decision

- `.claude/skills/assemble-ticket-context/SKILL.md:31,45,99-100` invoke
  `jira-tools fetch-ticket <KEY>`, `jira-tools extract-links <KEY>`,
  `jira-tools fetch-ticket <linked-key>` / `jira-tools fetch-page <page-id>`
  directly, with no `uv run` prefix. Confirmed empirically:
  `which jira-tools` → not found; only `uv run jira-tools` (from inside
  this project directory) resolves it today.
- **Decision (2026-07-02, user)**: ignore this. Assume `jira-tools` is
  installed and resolvable on `PATH` wherever the skill runs — no `uv run`
  prefix or working-directory fix needed in SKILL.md. The auth-check
  pre-flight (Finding 2) is the accepted guardrail for the case where that
  assumption is wrong: if `jira-tools` isn't actually installed/working,
  `auth-check` fails immediately and the skill stops with a clear message,
  rather than the skill trying to detect/fix the installation itself.
  Getting `jira-tools` properly installed is explicitly deferred to a
  separate future script/skill per `change.md`.

### 2. No auth pre-flight check, despite one already existing

- `src/jira_tools/cli.py:38-54` (`auth_check`) already does exactly what
  the change asks for: loads config (surfacing `ConfigNotFoundError` /
  `ConfigInvalidError` with actionable, credential-free messages via
  `src/jira_tools/config.py:27-38`), then calls `whoami()` against both
  Jira and Confluence, printing `PASS`/`FAIL` per product and exiting
  non-zero on any failure — all without ever printing the token
  (`SecretStr` in `config.py:20`).
- Verified working: `uv run jira-tools auth-check` → `Jira: PASS`,
  `Confluence: PASS`, exit 0, against the config at
  `~/.config/jira-tools/config.toml`.
- SKILL.md has no step that calls this before Step 1's `fetch-ticket`. Per
  the change notes, a failing auth-check should stop the skill immediately
  with a clear message (config missing / invalid / credentials rejected),
  not attempt to proceed and fail deeper into the flow with a less legible
  error from `fetch-ticket`.

### 3. FR-005–FR-008 coverage — no gaps found

- Step 1 + Step 3 → **FR-005** (fetch target ticket in full, dispatch one
  subagent per linked item, condensed perspective-framed findings, not
  echoed raw) — SKILL.md:26-38, 86-114 vs. `prd.md:145-157`.
- Step 4 → **FR-007** (main-context loading as the default outcome) —
  SKILL.md:116-122 vs. `prd.md:169-179`.
- Step 6 → **FR-006** (condensed synthesis + gaps section + staleness
  stamp) — SKILL.md:140-166 vs. `prd.md:161-168`.
- Step 3's graceful-degradation clause → **FR-008** (report gaps rather
  than fail) — SKILL.md:110-114 vs. `prd.md:180-188`.
- **Non-Goals respected**: Step 2 explicitly forbids following
  links-of-links (SKILL.md:81-84, matches the one-hop-only Non-Goal,
  `prd.md:261-262`); the dispatch list is an unfiltered union with no
  ranking/dropping (SKILL.md:73-79, matches the no-relevance-filtering
  Non-Goal, `prd.md:263-268`).

### 4. `extract-links` output parsing — mostly solid, one soft caveat

- The example block in SKILL.md:50-67 matches `links_document.py:15-40`'s
  actual output structurally, **including exact empty-section strings**
  (`*No Jira keys found.*` / `*No issue links found.*` / `*No Confluence
  pages found.*`, `links_document.py:10-12`) — byte-for-byte correct, no
  parsing risk there.
- Soft gap: the `(<relation>)` bullet suffix example (`blocks`, `relates
  to`) implies a tidy fixed vocabulary, but relation text is actually raw,
  Jira-instance-configured free text pulled straight from the issue-link
  type's `outward`/`inward` field (`atlassian_client.py:98-103`, e.g. could
  read "is blocked by", "duplicates", arbitrary capitalization). The skill
  already treats it as an opaque label so this isn't a functional bug — but
  a one-line note that relation text is free-form (not an enum) would
  prevent an executing agent from assuming otherwise.

### 5. Error/gap messaging — reliable but low-fidelity by CLI design

- All four failure sites in `cli.py` (`fetch_ticket:71-73`,
  `fetch_page:98-100`, `extract_links:130-133,139-142`) catch a broad
  `except Exception` and collapse every failure mode — not-found,
  forbidden, deleted, network error — into one fixed string per item type:
  `Could not fetch {ticket,page} <id>: not found or not accessible.`
- SKILL.md:110-114 asks subagents to report `<id>: <reason from stderr>`,
  which will therefore always produce the same generic reason string
  regardless of actual cause — deterministic, but not actually
  distinguishing "forbidden" from "deleted" from "not found" the way
  `prd.md:73-75` (guardrail) and `prd.md:219-220` (NFR) both frame gap
  reporting. This is a CLI-level limitation, not a SKILL.md bug, but the
  "reason from stderr" phrasing oversells the granularity actually
  available — worth a caveat in the skill text, or a future CLI change to
  make the underlying exceptions distinguishable (out of scope for this
  change per the PRD's guardrail framing, which only requires *reporting*
  the gap, not diagnosing it).

### 6. Subagent prompt completeness — two real gaps

- Present and correct: target-ticket framing (SKILL.md:95-98), relation
  label (SKILL.md:98), exact command to run (SKILL.md:99-100), explicit
  one-hop-only instruction (SKILL.md:101-102), graceful-degradation
  handling (SKILL.md:110-114).
- **Gap A (borderline must-fix)**: the prompt asks for one combined line —
  "what this item is (title/summary) and how it relates to `<KEY>`"
  (SKILL.md:104-105) — but the report template needs a clean `<title>` to
  slot into `### <linked-key> (<relation>) — <title>` (SKILL.md:157). As
  written, the orchestrator has to extract a title back out of prose after
  the fact; asking for title and relevance as two separate fields would
  remove that ambiguity.
- **Gap B (nice polish, defense in depth)**: there's no explicit "you are
  read-only, do not write files" instruction in the subagent prompt text
  itself — it's only enforced structurally by picking a
  non-Write/Edit-capable subagent type (SKILL.md:88-89). If the subagent
  type is changed later (see Finding 3's `general-purpose` recommendation,
  which *does* have Write/Edit access per the agent-type list), this
  structural guarantee disappears unless the prompt itself also states the
  constraint.

### 7. Developer usefulness of the final output

- Step 5/6 already cover status, description gist, dependencies/blockers,
  and gaps well relative to what's available.
- Real (CLI-scope) gap: `JiraTicket` (`atlassian_client.py:54-63`) only
  carries `key/summary/status/issue_type/description/comments/issue_links`
  — no assignee, priority, sprint/version, or due date. Since `fetch-ticket`
  never returns these fields, the skill has nothing to surface even if it
  wanted to. This is an FR-001 CLI scope limitation, not fixable inside
  SKILL.md, but worth naming explicitly as a known gap in "meeting prep"
  usefulness (could motivate a future FR-001 extension).
- Minor ambiguity: the report template line `### <linked-key> (<relation>)
  — <title>` (SKILL.md:157) doesn't say how to render a bare `## Jira keys`
  mention that has no relation label — unclear whether to print empty
  parens or omit the `(<relation>)` segment entirely.

### 8. Standalone-ness — input handling is fine; invocation is the real gap

- Missing-key / invalid-key handling is already graceful (SKILL.md:19-22
  asks for a key up front if absent; SKILL.md:36-38 handles a failed
  target-ticket fetch by stopping cleanly).
- The skill body has no unexplained dependency on `CLAUDE.md` conventions
  inside its *instructions* — the only reference to the PRD (SKILL.md:8) is
  provenance/citation, not something the executing agent needs to resolve
  to run the steps. With Finding 1 now out of scope by decision, the
  remaining standalone-ness gap is purely the missing auth pre-flight
  (Finding 2), which is concrete and fixable inside SKILL.md alone.

## Skill-convention findings (Claude Code ecosystem)

### Frontmatter — thin relative to convention

- Current frontmatter is only `name` + `description`
  (`.claude/skills/assemble-ticket-context/SKILL.md:1-4`).
- `allowed-tools` appears in the large majority of skills examined, e.g.
  `10x-research/SKILL.md:4-15` (`Read, Glob, Grep, Bash, Task, Write,
  AskUserQuestion, Task*`), `10x-frame/SKILL.md:9-13` (`Read, Glob, Grep,
  Write`), `10x-lesson/SKILL.md:4-8`. Given the read-only guardrail is a
  headline property of this skill (SKILL.md:14-17), encoding it via
  `allowed-tools: [Read, Bash, Task]` (no `Write`/`Edit`) would make that
  guarantee structural instead of prose-only.
- `argument-hint` is also common (~half the skills surveyed, e.g.
  `10x-new/SKILL.md:4`, `10x-roadmap/SKILL.md:9`) and would fit this
  skill's single-ticket-key input (`argument-hint: "<TICKET-KEY>"`).
- No skill in this environment uses a `disable-model-invocation`-style
  field, so its absence isn't a gap — that convention doesn't exist here.

### Subagent dispatch phrasing — already matches convention well

- SKILL.md:90-91 ("Send all of a batch's subagent calls in one message so
  they run in parallel") closely mirrors established phrasing elsewhere:
  `10x-research/SKILL.md:96` ("Spawn 2-4 agents in parallel in a single
  message"), `10x-frame/SKILL.md:140` ("all in one message for
  concurrency"), `10x-agents-md/SKILL.md:82` ("one batched call... not
  sequentially"). No change needed here — this is a genuine existing
  strength, not a gap.

### Tool-restriction pattern — `Explore` is the wrong subagent type

- Every other skill that names subagent types consistently defines
  `Explore` as fast file/pattern search only — e.g.
  `10x-research/SKILL.md:93` ("fast file/pattern search, code structure
  analysis... finding files, tracing code paths, searching for patterns"),
  `10x-plan/SKILL.md:316`, `10x-implement/SKILL.md:350`,
  `10x-tdd/SKILL.md:375`, `10x-e2e/SKILL.md:391`. The paired type,
  `general-purpose`, is consistently used for "run something and
  synthesize/reason over the result" work (`10x-research/SKILL.md:94`:
  "deep analysis requiring reading many files and multi-step reasoning").
- assemble-ticket-context's step 3 task — run one exact `jira-tools
  fetch-ticket`/`fetch-page` command, then condense/synthesize from a given
  perspective (SKILL.md:88-114) — matches the `general-purpose` job
  description, not `Explore`'s. No `.claude/agents/*.md` overrides exist
  anywhere on the machine that would redefine `Explore`, so it's relying on
  the built-in type whose documented purpose (consistent across every other
  skill here) doesn't match the task.
- Caveat for the plan: `general-purpose` has broader tool access (including
  `Write`/`Edit`) than `Explore`, so switching subagent type reopens the
  "structural read-only guarantee" question raised in Finding 6/Gap B above
  — the prompt itself would need an explicit read-only instruction to
  compensate.

### Structural conventions — close, one minor naming deviation

- Numbered `## Steps` sections are standard across the skill library
  (`10x-research`, `10x-plan`, `10x-implement`, etc.) — no deviation there.
- The dominant heading for argument handling is plural `## Inputs`
  (`pack-init/SKILL.md:20`, `tf-registry/SKILL.md:20`,
  `setup-cicd/SKILL.md:20`, `10x-mom-test/SKILL.md:42`) or `## Input
  resolution` for skills with fallback logic (`10x-agents-md/SKILL.md:26`,
  `10x-plan-review/SKILL.md:21`). assemble-ticket-context uses singular
  `## Input` (SKILL.md:19) — a minor naming deviation only, not functional.

## Code References

- `.claude/skills/assemble-ticket-context/SKILL.md:1-167` — the skill under review, in full.
- `src/jira_tools/cli.py:38-54` — existing `auth-check` command, not yet called by the skill.
- `src/jira_tools/cli.py:57-146` — `fetch-ticket` / `fetch-page` / `extract-links`, all invoked with bare `jira-tools` in SKILL.md.
- `src/jira_tools/config.py:40-44` — `config_path()`, XDG-aware config resolution; confirms auth-check has no dependency on cwd.
- `src/jira_tools/links_document.py:9-40` — exact Markdown shape `extract-links` produces; matches SKILL.md's documented example.
- `src/jira_tools/atlassian_client.py:54-63` — `JiraTicket` model; no assignee/priority/sprint/due-date fields.
- `src/jira_tools/atlassian_client.py:93-103` — issue-link relation text is raw Jira-configured free text, not an enum.
- `CLAUDE.md:7` — repo convention: `uv run <cmd>`, not bare invocation.
- `README.md:11-44` — CLI dev/config/auth-check usage, all via `uv run`.
- `context/foundation/prd.md:145-188` — FR-005–FR-008 text the skill must satisfy.
- `context/foundation/prd.md:256-268` — Non-Goals (one-hop only, no relevance filtering).

## Architecture Insights

- The PRD deliberately keeps the CLI primitives (FR-001–FR-004) mechanical
  and the "intelligence" (condensation, gap-spotting) one layer up in the
  skill (`prd.md:110-114, 222-244`). This research confirms the skill
  layer is where the design already lives correctly — the gaps found are
  either (a) the skill not yet calling a CLI primitive that already exists
  (`auth-check`), or (b) the skill's own invocation/tooling choices
  (bare command, `Explore` subagent type), not gaps in the underlying CLI
  design.
- The CLI's `except Exception` → generic-message pattern in `cli.py` is
  consistent across all three fetch/extract commands — it's a deliberate,
  uniform simplification (never leak raw exception detail that might
  include partial credential/URL info), not an oversight in one spot. Any
  future push for more granular gap messages would be a CLI-wide change,
  not a one-line fix.

## Historical Context (from prior changes)

- `context/foundation/roadmap.md` (uncommitted diff) shows S-04 was
  recently merged from two originally separate slices
  (`assemble-one-hop-context` + `load-context-into-claude`) into one skill
  that does both fetch/condense and live-load in a single run, using
  subagent condensation as the resolution to the PRD's Open Question #3
  (context-window overflow). This change (`assemble-ticket-context`) is
  that merged S-04 slice's implementation — already built once
  (`SKILL.md` exists), now being polished per the change notes.
- `context/changes/extract-ticket-links/` (S-03, `status: impl_reviewed`)
  is the immediate prerequisite this skill's Step 2 depends on
  (`extract-links` CLI command) — already shipped and reviewed, no open
  issues there that affect this skill.

## Related Research

- None found under `context/changes/**/research.md` or
  `context/archive/**/research.md` — this is the first `/10x-research` run
  in this repo.

## Open Questions

1. ~~Should the auth pre-flight (`auth-check`) run on every invocation, or
   only be suggested once and cached/skipped on subsequent runs in the same
   session?~~ **Resolved (2026-07-02, user)**: run `jira-tools auth-check`
   at the very start of every invocation; if it exits non-zero (not
   installed, not configured, or credentials rejected), stop the skill
   immediately with the check's own PASS/FAIL output — no caching, no
   attempt to proceed or self-remediate.
2. ~~Should SKILL.md hardcode an absolute path to this project's `uv`
   project root...~~ **Resolved (2026-07-02, user)**: out of scope — assume
   `jira-tools` is already installed/on `PATH`; see Finding 1. No
   invocation-mechanics fix needed.
3. Given `general-purpose` subagents have `Write`/`Edit` access (unlike
   `Explore`), does switching subagent type (Finding — tool-restriction
   pattern) require an explicit read-only instruction in the prompt text to
   preserve the guardrail, or is there a more tightly-scoped subagent type
   available that combines Bash + read-only? Owner: user/planner, to
   resolve during planning.
