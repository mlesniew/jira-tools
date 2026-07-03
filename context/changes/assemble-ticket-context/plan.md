# Polish the assemble-ticket-context skill — Implementation Plan

## Overview

`.claude/skills/assemble-ticket-context/SKILL.md` already implements the PRD's
US-01 / FR-005–FR-008 flow correctly, but has a missing auth pre-flight check
and a handful of real quality gaps flagged by `context/changes/assemble-ticket-context/research.md`.
This plan makes the skill check `jira-tools auth-check` before doing anything
else, fixes the wrong subagent type used for dispatch (and preserves the
read-only guarantee through the type change), and tightens the dispatch
prompt and report template so they're unambiguous to execute.

## Current State Analysis

- The skill has thin frontmatter (`name` + `description` only) and no
  pre-flight check — it goes straight to `jira-tools fetch-ticket <KEY>` and
  will fail deep in the flow with a generic CLI error if `jira-tools` isn't
  configured, instead of stopping cleanly up front.
- Step 3 dispatches `Explore`-type subagents to run a fetch command and
  condense its output — a "run + synthesize" job that every other skill in
  this repo pairs with `general-purpose`, not `Explore` (which is documented
  everywhere else as search-only).
- The per-subagent prompt asks for one combined "title + relevance" line, but
  the step 6 report template needs a clean `<title>` slot — forcing the
  orchestrator to parse a title back out of prose.
- The step 6 report template's heading (`### <linked-key> (<relation>) —
  <title>`) has no defined behavior for a bare `## Jira keys` mention that
  carries no relation label.
- Two informational gaps are undocumented in the skill text: relation labels
  are raw free-form Jira-configured text (not an enum), and every CLI fetch
  failure collapses into one fixed generic message regardless of actual
  cause.
- Two research open questions are already resolved and don't need further
  work: (1) no `uv run` prefix / PATH fix — explicitly out of scope per prior
  user decision; (2) auth-check runs at the start of every invocation with no
  caching, stopping immediately on failure.

## Desired End State

`SKILL.md` runs standalone (assuming `jira-tools` is already on `PATH`) and
verifies auth before doing anything else — if `jira-tools` isn't configured
or credentials are rejected, the skill stops immediately after Step 0 and
shows the auth-check's own PASS/FAIL output, rather than failing confusingly
deeper in the flow. Step 3's dispatch uses the subagent type whose documented
job actually matches "run a command and synthesize from a given perspective,"
with the read-only guarantee preserved via an explicit prompt instruction now
that the tool-level restriction no longer applies. The report template
renders every linked-item heading unambiguously, whether or not the item has
a relation label.

Verify by: reading `SKILL.md` against each phase's success criteria below,
and running the skill live (`/assemble-ticket-context <REAL-KEY>`) against a
real ticket with both a related and an unrelated (bare-mention) linked item.

### Key Discoveries:

- `auth-check` already exists and does exactly what's needed —
  `src/jira_tools/cli.py:38-54` — validating config and both Jira/Confluence
  credentials without ever printing the token, exiting non-zero on any
  failure. Not yet called by the skill.
- The skill's "read-only" guarantee is about Atlassian, not the local
  filesystem (`SKILL.md:14-17`: "never writes to Atlassian"). Every other
  multi-step skill in this repo that writes an output file declares `Write`
  in `allowed-tools` (`10x-research/SKILL.md`, `10x-frame/SKILL.md`) — so
  Step 6's report-saving needs `Write` in scope, not just `Read`/`Bash`/`Task`.
- `general-purpose` subagents have full tool access per this environment's
  agent-type list; `Explore` excludes `Write`/`Edit`/`Agent`/`Artifact`/
  `ExitPlanMode`/`NotebookEdit`. The read-only guarantee currently comes
  entirely from `Explore`'s tool restriction and needs an explicit
  prompt-level instruction once the subagent type changes.
- Relation label text is raw Jira-instance-configured free text pulled from
  the issue-link type's `outward`/`inward` field
  (`src/jira_tools/atlassian_client.py:93-103`) — not an enum.
- All CLI fetch failures collapse into one generic message via a uniform
  `except Exception` pattern (`src/jira_tools/cli.py`: `fetch_ticket:71-73`,
  `fetch_page:98-100`, `extract_links:130-133,139-142`) — deliberate and
  consistent across every call site, not fixable inside `SKILL.md`.

## What We're NOT Doing

- Not adding a `uv run` prefix or otherwise fixing invocation mechanics
  (PATH/working directory) — explicitly out of scope per the research doc's
  resolved Open Question #2 (user decision, 2026-07-02).
- Not modifying the CLI (`cli.py`, `atlassian_client.py`) — no new
  `JiraTicket` fields (assignee/priority/sprint/due-date), no more granular
  per-cause exception messages. Both are CLI-scope changes for a future
  change, not this one.
- Not adding a "known limitations" note about missing ticket fields
  (assignee/priority/sprint/due-date) to the skill body — considered and
  declined during planning; the skill stays focused on what it does rather
  than what the CLI doesn't yet fetch.
- Not building a `jira-tools` setup/auth-configuration script or skill —
  deferred to a separate future change per `change.md`.
- Not changing one-hop link-extraction behavior or the no-relevance-filtering
  dispatch logic — research found both already correct against the PRD.

## Implementation Approach

Both phases edit a single file, `.claude/skills/assemble-ticket-context/SKILL.md`
— no source code changes. Phase 1 adds the frontmatter tool-scope/argument
hint and a new Step 0 pre-flight check ahead of the existing Step 1. Phase 2
tightens Step 3's dispatch prompt (subagent type, read-only instruction,
title/relevance split, two informational caveats) and fixes Step 6's report
template heading. Edits proceed top-to-bottom through the file.

## Critical Implementation Details

**auth-check exit semantics**: `auth-check` exits non-zero if *either*
Jira or Confluence fails, and its own stdout already prints a `PASS`/`FAIL`
line per product. Step 0 should surface that command's output verbatim as
the stop reason rather than re-deriving which product failed — the
distinction is already made by the CLI, re-parsing it in the skill would be
redundant and could drift out of sync with the CLI's actual wording.

## Phase 1: Frontmatter & auth pre-flight

### Overview

Add `allowed-tools` and `argument-hint` to the skill's frontmatter, and
insert a new Step 0 that runs `jira-tools auth-check` before Step 1 ever
runs, stopping the skill immediately on failure.

### Changes Required:

#### 1. Frontmatter tool scope and argument hint

**File**: `.claude/skills/assemble-ticket-context/SKILL.md`

**Intent**: Make the skill's tool scope and single-argument contract
structural/discoverable instead of implicit in prose, matching the
convention used by every other multi-step skill in this repo
(`10x-research/SKILL.md`, `10x-frame/SKILL.md`, `10x-new/SKILL.md`). Scope
must include `Write` (Step 6 saves a report to disk) and `AskUserQuestion`
(Step 6 asks the user what to do next) alongside `Read`/`Bash`/`Task`.

**Contract**: Add to the YAML frontmatter block (lines 1-4):

```
allowed-tools:
  - Read
  - Bash
  - Task
  - Write
  - AskUserQuestion
argument-hint: "<TICKET-KEY>"
```

#### 2. New Step 0: verify jira-tools is configured

**File**: `.claude/skills/assemble-ticket-context/SKILL.md`

**Intent**: Run the existing `auth-check` command first, before any fetch
happens. If it fails for any reason — including `jira-tools` not being
installed/on `PATH` at all, not just an in-tool credential failure — stop
the skill immediately and show whatever it printed as the reason. No
attempt to proceed, no self-remediation, no caching across runs (per
research's resolved Open Question #1). Research confirmed empirically that
`jira-tools` is *not* on `PATH` in at least one environment today
(`which jira-tools` → not found) — this is the headline scenario auth-check
exists to catch, so Step 0 must handle "command not found" (a shell error,
no PASS/FAIL output at all) the same as an in-tool credential FAIL, not just
the latter.

**Contract**: New `### 0. Verify jira-tools is configured` section under
`## Steps`, placed immediately before the existing `### 1. Fetch the target
ticket in full`. Runs `jira-tools auth-check`; on exit 0, continues to Step
1; on *any* failure to complete successfully — non-zero exit with PASS/FAIL
output, or the command/binary not being found at all — stops and relays
whatever output or error the shell produced to the user as the reason
context assembly can't proceed.

### Success Criteria:

#### Automated Verification:

- [ ] Frontmatter block parses as valid YAML and includes both `allowed-tools`
      (containing `Read`, `Bash`, `Task`, `Write`, `AskUserQuestion`) and
      `argument-hint: "<TICKET-KEY>"`: `grep -A8 "^allowed-tools" .claude/skills/assemble-ticket-context/SKILL.md`
- [ ] `### 0. Verify jira-tools is configured` exists and precedes
      `### 1. Fetch the target ticket in full`, and the section body contains
      the literal command `jira-tools auth-check`: `grep -n "^### 0\|^### 1\|jira-tools auth-check" .claude/skills/assemble-ticket-context/SKILL.md`

#### Manual Verification:

- [ ] Running the skill against a real ticket key with a valid Atlassian
      config completes Step 0 silently (auth-check passes) and proceeds
      straight to Step 1 with no extra prompts
- [ ] Simulating an auth failure (e.g. temporarily pointing config at
      invalid credentials) causes the skill to stop immediately after Step
      0, surfacing auth-check's own PASS/FAIL output, without attempting
      Step 1
- [ ] Simulating `jira-tools` not being installed/on `PATH` (e.g. a broken
      alias or `PATH` without the binary) causes the skill to stop
      immediately after Step 0, surfacing the shell's "command not found"
      (or equivalent) error, without attempting Step 1

**Implementation Note**: After completing this phase and all automated
verification passes, pause here for manual confirmation from the human that
the manual testing was successful before proceeding to the next phase.

---

## Phase 2: Dispatch & template polish

### Overview

Fix Step 3's subagent type and prompt (type, read-only instruction,
title/relevance split, two informational caveats), and fix Step 6's report
template so the no-relation heading case is defined.

### Changes Required:

#### 1. Step 3 subagent type and read-only instruction

**File**: `.claude/skills/assemble-ticket-context/SKILL.md`

**Intent**: Switch the dispatched subagent type from `Explore` to
`general-purpose` to match this repo's convention for "run a command, then
synthesize/condense from a given perspective" work. Since `general-purpose`
has full tool access (unlike `Explore`, which structurally excludes
`Write`/`Edit`), preserve the read-only guarantee by adding an explicit
instruction to the per-subagent prompt itself.

**Contract**: Step 3's opening sentence changes from "spawn an `Explore`-type
subagent (read-only, has Bash, no Edit/Write — matches the read-only
guardrail structurally)" to reference `general-purpose` instead, noting the
type change means the read-only guarantee now comes from the prompt, not the
tool set. Add a new bullet to the per-subagent prompt list: an explicit
instruction that the subagent is strictly read-only and must not create,
write, or edit any file — it may only run the given fetch command and report
findings back in its response.

#### 2. Split title and relevance fields in the subagent prompt

**File**: `.claude/skills/assemble-ticket-context/SKILL.md`

**Intent**: Give the orchestrator a clean `<title>` value to slot directly
into Step 6's report template heading, removing the need to parse a title
back out of a combined prose line.

**Contract**: In Step 3's "What to return" bullet list, replace the single
combined item ("one line: what this item is (title/summary) and how it
relates to `<KEY>`") with two separate bullets: a title/summary line (no
relevance framing), and a one-line statement of how it relates to `<KEY>`.

#### 3. Relation-label free-text caveat

**File**: `.claude/skills/assemble-ticket-context/SKILL.md`

**Intent**: Prevent an executing agent from assuming relation labels come
from a fixed vocabulary and mishandling an unexpected string.

**Contract**: One added sentence on Step 3's "The relation label, if there
is one" bullet, noting the label is raw free text configured per Jira
instance (e.g. could read "is blocked by", arbitrary capitalization), not an
enum — treat it as an opaque label.

#### 4. Gap-message fidelity caveat

**File**: `.claude/skills/assemble-ticket-context/SKILL.md`

**Intent**: Set correct expectations that the CLI's fetch-failure reason
string is always the same generic message by design, not a diagnosis of the
specific cause — so a reader doesn't mistake a future CLI change as fixing a
regression that never existed at this layer.

**Contract**: One added clause on Step 3's existing "Graceful degradation"
bullet, noting the reason string is a fixed generic message regardless of
actual cause (not found / forbidden / deleted / network error all read the
same).

#### 5. Report template: no-relation heading case

**File**: `.claude/skills/assemble-ticket-context/SKILL.md`

**Intent**: Define the previously-ambiguous rendering for a linked item that
has no relation label (a bare `## Jira keys` mention, not a formal issue
link).

**Contract**: Step 6's report template heading becomes conditional:
`### <linked-key> (<relation>) — <title>` when a relation label exists,
`### <linked-key> — <title>` (parens omitted entirely) when it doesn't. Add
a one-line note directly above the template block stating this conditional.

### Success Criteria:

#### Automated Verification:

- [ ] `Explore` no longer appears anywhere in the file and `general-purpose`
      does — asserts the type was actually replaced, not just that both
      terms happen to co-exist:
      `! grep -q "Explore" .claude/skills/assemble-ticket-context/SKILL.md && grep -q "general-purpose" .claude/skills/assemble-ticket-context/SKILL.md`
- [ ] The distinctive new read-only instruction phrase is present (not the
      pre-existing generic word "read-only", which appears before this
      change too and wouldn't discriminate):
      `grep -q "must not create, write, or edit" .claude/skills/assemble-ticket-context/SKILL.md`
- [ ] Step 6's template block and preceding note show the conditional
      no-relation heading form: `grep -q "### <linked-key> — <title>" .claude/skills/assemble-ticket-context/SKILL.md`

#### Manual Verification:

- [ ] Step 3's "What to return" list has separate title and relevance
      bullets (no single combined "title/summary and how it relates" line)
- [ ] Step 3 contains both the relation free-text caveat and the
      gap-message fidelity caveat as distinct sentences
- [ ] Running the skill end-to-end against a real ticket with at least one
      formal issue link (has a relation) and one bare Jira-key mention (no
      relation) produces a report where both heading forms render correctly
      and each `<title>` matches the linked item's actual title
- [ ] Reading the transcript of a dispatched subagent confirms it made no
      Write/Edit tool call during its run

**Implementation Note**: After completing this phase and all automated
verification passes, pause here for manual confirmation from the human that
the manual testing was successful.

---

## Testing Strategy

### Unit Tests:

Not applicable — this change only edits a Markdown skill prompt, no Python
source under `src/jira_tools/`.

### Integration Tests:

Not applicable for the same reason; `uv run pytest` is unaffected by this
change since no `.py` files change.

### Manual Testing Steps:

1. Run `/assemble-ticket-context <REAL-KEY>` against a real ticket with a
   valid `jira-tools` config; confirm Step 0 passes silently and the flow
   proceeds through fetch, dispatch, summary, and the save-report offer.
2. Temporarily break the Atlassian config (e.g. invalid API token) and
   re-run; confirm the skill stops immediately after Step 0 with
   `auth-check`'s own PASS/FAIL output, and does not attempt Step 1.
3. Temporarily make `jira-tools` unresolvable (e.g. rename it off `PATH` or
   run in a shell where it was never installed) and re-run; confirm the
   skill stops immediately after Step 0 with the shell's "command not
   found" (or equivalent) error surfaced, and does not attempt Step 1.
4. Pick a real ticket with both a formal issue link and a bare Jira-key
   mention in its body; confirm the saved report renders both heading forms
   correctly (with and without a relation label) and titles are accurate.
5. Read a dispatched subagent's transcript and confirm no Write/Edit tool
   call occurred.

## Performance Considerations

None — this change doesn't alter fetch volume, dispatch parallelism, or
data model; it's a prompt/frontmatter edit to an existing flow.

## Migration Notes

None — no data model, config format, or persisted state changes.

## References

- Research: `context/changes/assemble-ticket-context/research.md`
- Skill under change: `.claude/skills/assemble-ticket-context/SKILL.md`
- `auth-check` command: `src/jira_tools/cli.py:38-54`
- Fetch failure handling: `src/jira_tools/cli.py:71-73,98-100,130-133,139-142`
- Relation label source: `src/jira_tools/atlassian_client.py:93-103`
- Convention reference (allowed-tools with Write): `.claude/skills/10x-research/SKILL.md`, `.claude/skills/10x-frame/SKILL.md`
- PRD requirements: `context/foundation/prd.md:145-188` (FR-005–FR-008)

## Progress

> Convention: `- [ ]` pending, `- [x]` done. Append ` — <commit sha>` when a step lands. Do not rename step titles.

### Phase 1: Frontmatter & auth pre-flight

#### Automated

- [x] 1.1 Frontmatter parses as valid YAML with `allowed-tools` and `argument-hint` — c26efef
- [x] 1.2 Step 0 exists before Step 1 and contains `jira-tools auth-check` — c26efef

#### Manual

- [ ] 1.3 Valid config: Step 0 passes silently, flow proceeds to Step 1
- [ ] 1.4 Invalid config: skill stops after Step 0 with auth-check's PASS/FAIL output
- [ ] 1.5 jira-tools not installed/on PATH: skill stops after Step 0 with the shell's error surfaced

### Phase 2: Dispatch & template polish

#### Automated

- [x] 2.1 `Explore` absent and `general-purpose` present (type actually replaced) — 5d114f8 — **superseded, see Addenda**
- [x] 2.2 Distinctive read-only instruction phrase present in Step 3 — 5d114f8
- [x] 2.3 Step 6 template renders the conditional no-relation heading form — 5d114f8

#### Manual

- [ ] 2.4 Step 3's "What to return" list has separate title and relevance bullets
- [ ] 2.5 Step 3 includes relation free-text and gap-message fidelity caveats
- [ ] 2.6 End-to-end run renders both heading forms correctly with accurate titles
- [ ] 2.7 Dispatched subagent transcript shows no Write/Edit tool call

## Addenda

### 2026-07-03 — Step 3 subagent type reverted to `Explore` (impl-review F1)

`context/changes/assemble-ticket-context/reviews/impl-review.md` (F1) found
this plan's Change 1 rationale ("`general-purpose` matches this repo's
convention for run + synthesize work") doesn't hold up: checked against the
actual cited sibling skills (`10x-research/SKILL.md`, `10x-frame/SKILL.md`),
their real split is `Explore` = structural search vs. `general-purpose` =
judgment/reasoning over what's found — not read-only-vs-write. Step 3's job
(run one fetch command, read the output, return a condensed judgment) needs
nothing `general-purpose` grants beyond what `Explore` already has (Bash,
Read, reasoning). Since Step 3's dispatched subagents read untrusted
ticket/Confluence content, and CLAUDE.md names "strictly read-only" as an
explicit guardrail, the structural guarantee `Explore` provides was judged
worth more than the prompt-level one `general-purpose` required.

**Resolution**: Step 3's dispatch was reverted to `Explore`-type subagents;
the now-redundant "must not create, write, or edit any file" prompt
instruction was removed (enforced structurally instead). This supersedes
Automated criterion 2.1 and Change 1's contract above — `Explore` is the
correct, current state, not `general-purpose`. Manual criterion 2.7 ("no
Write/Edit tool call in transcript") is unaffected in spirit but now trivially
true by construction rather than needing transcript inspection.
