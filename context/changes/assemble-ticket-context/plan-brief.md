# Polish the assemble-ticket-context skill — Plan Brief

> Full plan: `context/changes/assemble-ticket-context/plan.md`
> Research: `context/changes/assemble-ticket-context/research.md`

## What & Why

Polish `.claude/skills/assemble-ticket-context/SKILL.md` so it checks that
`jira-tools` is configured before doing anything else, and fixes a handful of
real gaps research found: the wrong subagent type for step 3's dispatch, an
ambiguous prompt/report-template contract, and two undocumented CLI
limitations that could mislead whoever reads the skill's output.

## Starting Point

The skill already implements the PRD's US-01 / FR-005–FR-008 flow correctly
(fetch target ticket, one-hop link extraction, per-item subagent dispatch,
condensed live-load, optional saved report) — it was built once and is now
being polished, not redesigned. It has no auth pre-flight, dispatches
`Explore`-type subagents for a job that's really "run a command and
synthesize" (this repo's convention pairs that with `general-purpose`), and
has two small template/prompt ambiguities. `auth-check`, the exact CLI
primitive needed for the pre-flight, already exists (`src/jira_tools/cli.py:38-54`)
and just isn't called yet.

## Desired End State

Running the skill against a ticket key first silently verifies Jira/Confluence
auth; if that fails, the skill stops immediately with a clear PASS/FAIL
message instead of failing confusingly deeper in the flow. Dispatched
subagents use the correctly-named type for their job, stay read-only via an
explicit prompt instruction, and return a clean title separate from their
relevance note. The saved report renders every linked item's heading
correctly whether or not it has a relation label.

## Key Decisions Made

| Decision | Choice | Why (1 sentence) | Source |
| --- | --- | --- | --- |
| Auth pre-flight timing/caching | Run at start of every invocation, no caching, stop immediately on failure | Matches the change's ask for a hard stop rather than deep-flow failure | Research |
| Invocation mechanics (`uv run` / PATH) | Out of scope — assume `jira-tools` is on `PATH` | Auth-check is the accepted guardrail if that assumption is wrong | Research |
| Dispatch subagent type | Switch `Explore` → `general-purpose` + explicit read-only prompt instruction | Matches this repo's "run + synthesize" convention; read-only guarantee moves from tool-level to prompt-level | Plan |
| Frontmatter tool scope | `Read, Bash, Task, Write, AskUserQuestion` | Step 6 saves a report file and asks the user what's next — both need scope the research's first-pass suggestion omitted | Plan |
| Prompt title/relevance fields | Split into two separate bullets | Report template needs a clean `<title>` slot, not prose to parse | Plan |
| No-relation heading rendering | Omit parens entirely (no placeholder label) | Reads naturally, doesn't invent a relation type the source data doesn't have | Plan |
| Gap-message fidelity caveat | Add a one-line note that the reason string is always generic by CLI design | Sets correct expectations without overselling diagnostic detail | Plan |
| Missing ticket fields (assignee/priority/etc.) | Do not mention in the skill body | Keep the skill focused on what it does; declined during planning | Plan |

## Scope

**In scope:**
- Frontmatter: `allowed-tools`, `argument-hint`
- New Step 0: `jira-tools auth-check` pre-flight, stop-on-failure
- Step 3: subagent type change, read-only instruction, title/relevance split, relation free-text caveat, gap-fidelity caveat
- Step 6: report template no-relation heading fix

**Out of scope:**
- `uv run` prefix / PATH / invocation-mechanics fixes (prior decision)
- Any CLI (`cli.py`, `atlassian_client.py`) changes — no new ticket fields, no more granular error messages
- A "known limitations" note about missing ticket fields (assignee/priority/sprint/due-date)
- A `jira-tools` setup/auth-configuration script or skill (separate future change)
- One-hop link-extraction or dispatch-filtering behavior (already correct per research)

## Architecture / Approach

Both phases edit one file, `.claude/skills/assemble-ticket-context/SKILL.md`
— no source code changes, no new files. Phase 1 adds the frontmatter and a
new Step 0 ahead of the existing flow. Phase 2 tightens Step 3's dispatch
prompt and fixes Step 6's template, working top-to-bottom through the file.

## Phases at a Glance

| Phase | What it delivers | Key risk |
| --- | --- | --- |
| 1. Frontmatter & auth pre-flight | Skill declares its real tool scope and stops cleanly if `jira-tools` isn't configured | Auth-check's PASS/FAIL wording could be mis-relayed if the skill tries to re-parse instead of showing it verbatim |
| 2. Dispatch & template polish | Correct subagent type with a preserved read-only guarantee, unambiguous prompt/template contract | Prompt-level read-only instruction is not enforced by the tool system — relies on subagent compliance |

**Prerequisites:** None — `auth-check` and `extract-links` already exist and are verified working; no upstream change needed.
**Estimated effort:** ~1 session, 2 phases, single file.

## Open Risks & Assumptions

- The read-only guarantee for Step 3 subagents now depends on prompt
  compliance rather than tool restriction, since `general-purpose` has
  Write/Edit access. Manual verification (2.7) checks this per real run, but
  it's not a structural guarantee going forward.
- Manual verification for Phase 1's failure path requires deliberately
  breaking a working Atlassian config — do this against a config the user
  can safely restore afterward.

## Success Criteria (Summary)

- The skill stops immediately and clearly when `jira-tools` isn't configured, instead of failing deep in the flow
- A real end-to-end run against a ticket with both a related and an unrelated linked item produces a correctly-rendered report with accurate titles
- No dispatched subagent performs a Write/Edit action during a real run
