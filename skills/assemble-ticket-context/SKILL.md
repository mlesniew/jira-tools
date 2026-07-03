---
name: assemble-ticket-context
description: Assemble the full one-hop context for a Jira ticket — the ticket itself plus every directly-linked ticket and referenced Confluence page — using the globally-installed jira-tools CLI, condense each linked item from the target ticket's perspective via subagents, and present a summary before offering to save a report. Use when the user gives a Jira ticket key and wants to prep for a planning/refinement/design meeting, or asks to "load context for <KEY>", "assemble context for <KEY>", "prep me for <KEY>", "what's the context on <KEY>".
allowed-tools:
  - Read
  - Bash
  - Task
  - Write
  - AskUserQuestion
argument-hint: "<TICKET-KEY>"
---

# Assemble ticket context

Implements the PRD's US-01 / FR-005–FR-008 flow (see
`context/foundation/prd.md`) as a single skill run: fetch the target ticket
in full, fetch its one-hop links via per-item subagents that condense from
the target ticket's perspective, present a summary, then let the user decide
what happens next.

This skill only ever calls the globally-installed `jira-tools` CLI
(`fetch-ticket`, `fetch-page`, `extract-links`) — it never talks to
Jira/Confluence directly, and never writes to Atlassian (read-only
guardrail, enforced in the CLI layer already).

## Input

A single Jira ticket key, e.g. `PROJ-123`. If the user didn't give one, ask
for it before doing anything else.

## Steps

### 0. Verify jira-tools is configured

Run:

```
jira-tools auth-check
```

If this fails for any reason — a non-zero exit with `PASS`/`FAIL` output for
Jira and/or Confluence, or the command/binary not being found at all (e.g.
`jira-tools` isn't on `PATH`) — stop immediately and relay the PASS/FAIL
lines as the reason context assembly can't proceed. If a FAIL reason is
more than a short error phrase (e.g. it contains raw HTTP/network detail
from the underlying client), summarize it in your own words rather than
pasting it verbatim — it may echo more of the request than intended. Do
not attempt Step 1, do not retry, and do not cache the result across runs —
this check always runs fresh at the start of every invocation.

If it passes, continue silently to Step 1.

### 1. Fetch the target ticket in full

Run:

```
jira-tools fetch-ticket <KEY>
```

Read its full Markdown output directly — this is the anchor everything else
gets judged against, so it is **not** condensed. If this command fails
(non-zero exit, stderr message like `Could not fetch ticket <KEY>: not found
or not accessible.`), stop here and tell the user the target ticket itself
couldn't be fetched — there's no context to assemble.

### 2. Extract its one-hop links

Run:

```
jira-tools extract-links <KEY>
```

The output is a fixed-shape Markdown document:

```
# Links found in <KEY>

## Jira keys

- KEY1
- KEY2

## Issue links

- KEY3 (blocks)
- KEY4 (relates to)

## Confluence pages

- 12345
- 67890
```

(Empty sections instead show `*No Jira keys found.*` / `*No issue links
found.*` / `*No Confluence pages found.*` — treat those as "nothing to
dispatch for this category", not as an error.)

Build the dispatch list:
- **Jira tickets to fetch** = the union of `## Jira keys` and the keys in
  `## Issue links`, deduplicated. (These are two different sources — text/
  link mentions in the body vs. formal issue-link relations — and can
  overlap; fetch each key once.) Keep the relation label (e.g. `blocks`)
  where one exists, for context in step 3.
- **Confluence pages to fetch** = everything under `## Confluence pages`.

Do not extract links from anything else — this is the only link-extraction
call in the whole flow. Following links found *inside* a linked ticket or
page would be two-hop traversal, which is explicitly out of scope (PRD
Non-Goal: no multi-hop / recursive crawling).

### 3. Dispatch one subagent per linked item, in parallel

For every item in the dispatch list, spawn an `Explore`-type subagent —
Step 3's job is entirely read + reason (run one fetch command, read its
output, return a condensed judgment), which is exactly what `Explore`
grants (Bash, Read, reasoning) while structurally excluding Edit/Write, so
the read-only guarantee holds at the tool level rather than the prompt
level. Send all of a batch's subagent calls in one message so they run in
parallel.

Each subagent's prompt should include:
- The target ticket's key and summary (and description, if it fits — a
  sentence or two is enough for framing), so the subagent reads the linked
  item with "why would this matter to `<KEY>`" in mind rather than in
  isolation.
- The relation label, if there is one (e.g. "this ticket blocks `<KEY>`").
  This label is raw free text configured per Jira instance (e.g. could read
  "is blocked by", arbitrary capitalization) — not a fixed enum. Treat it as
  an opaque label, not something to normalize or validate.
- The exact command to run: `jira-tools fetch-ticket <linked-key>` for a
  Jira ticket, or `jira-tools fetch-page <page-id>` for a Confluence page.
- An explicit instruction **not** to follow any further links it finds in
  the fetched content — one hop only, no recursion.
- What to return: a condensed, ticket-focused note — not the raw fetched
  content. Roughly:
  - one line: what this item is (title/summary),
  - one line: how it relates to `<KEY>`,
  - 3–6 bullets of key facts relevant to `<KEY>` (not everything in the
    document — only what bears on the target ticket),
  - any open questions, risks, or blockers this raises for `<KEY>`.
- **Graceful degradation**: if the `jira-tools` command exits non-zero
  (inaccessible, forbidden, deleted, or any other fetch failure), the
  subagent must report that as a gap — `<id>: <reason from stderr>` — and
  stop, rather than guessing at content or treating it as a hard failure of
  the whole run. The reason string is always the same fixed generic message
  regardless of actual cause (not found / forbidden / deleted / network
  error all read the same) — it's a report of failure, not a diagnosis of
  the specific cause.

### 4. Assemble into the main conversation

Collect every subagent's condensed finding (or gap) into the main context,
grouped by relation/type (e.g. blocks / relates to / referenced Confluence
pages). This — the target ticket's full content plus the condensed
per-item findings plus the gap list — is the assembled one-hop context,
now loaded into the conversation (FR-007's default outcome).

### 5. Present a high-level summary

Before asking anything, give the user a short summary: what `<KEY>` is
about, what needs to get done, and the key things the linked items surface
(dependencies, blockers, relevant prior art, open questions) — plus a one-
line note on any gaps. Keep this tight; it's an orientation, not the full
report.

### 6. Ask what's next

Offer two options, plainly:
- **Keep chatting** about the assembled context in this conversation.
- **Save a detailed report** to a Markdown file.

If the user asks for the report, confirm or ask for a destination path
(default: `<KEY>-context.md` in the current directory) before writing it. If
a file already exists at that path, say so and ask the user to confirm
overwrite or give a different path — don't write over it silently.
The report is the **condensed synthesis** — organized by linked item, with
a Gaps section — not a raw dump of every fetched document (per the PRD's
FR-006). Stamp it with the target ticket's key and the fetch timestamp so
staleness against Atlassian is visible at a glance, e.g.:

Each linked-ticket heading is conditional on whether the item has a relation
label: use `### <linked-key> (<relation>) — <title>` when it does (a formal
issue link), and `### <linked-key> — <title>` (parens omitted entirely) when
it doesn't (a bare `## Jira keys` mention).

```markdown
# Context report: <KEY> — <summary>

Fetched: <ISO timestamp>

## Summary
<the high-level summary from step 5>

## <KEY> — target ticket
<short recap: status, description gist>

## Linked tickets
### <linked-key> (<relation>) — <title>
- <condensed bullets from that subagent>

### <linked-key> — <title>
- <condensed bullets from that subagent>

## Confluence pages
### <page title> (page <id>)
- <condensed bullets from that subagent>

## Gaps
- <id>: <reason>
```
