---
project: Jira & Confluence Context Skills
version: 1
status: draft
created: 2026-06-23
context_type: greenfield
product_type: cli
target_scale:
  users: small
timeline_budget:
  mvp_weeks: 1
  hard_deadline: null
  after_hours_only: true
---

## Vision & Problem Statement

Software engineers and architects spend large amounts of focused time
understanding a Jira ticket and preparing for planning, refinement, and design
meetings. The context needed is scattered across the ticket itself, its linked
tickets, comments, and related Confluence pages, so prep is a slow, manual,
cognitively heavy reconstruction job.

The insight: the bottleneck is human synthesis of dispersed context, not the
analysis itself. Once that scattered context is *assembled* into a clean,
readable form, an LLM can do much of the understanding and prep work — context
gathering, synthesis, gap and risk spotting, and technical research — that
currently consumes an engineer's focus. The product's job is to produce that
clean, trustworthy corpus.

## User & Persona

**Primary persona** — Individual engineer / architect preparing solo. An IC
(including the author) who needs the full picture of a ticket before a meeting.
They work on their own machine, for their own understanding. The assembled
context is loaded live into a Claude conversation for immediate analysis and
Q&A as the default outcome of running the skill, with a persisted Markdown
report (readable and searchable by both human and agent) available as an
explicit follow-up when the user wants it kept for later.

## Success Criteria

### Primary

The end-to-end multi-source assembly flow works for a single ticket:

1. The user supplies a Jira ticket key.
2. The tool fetches that ticket in full (title, description, comments).
3. It fetches every ticket **directly linked** to the target (one hop, no
   recursion) and every Confluence page **directly referenced/linked** from the
   target ticket, converting each from Atlassian's rich-content format (ADF) to
   readable Markdown, then condensing it from the target ticket's perspective.
4. The assembled context (full target + condensed findings + any gaps) is
   loaded into the Claude conversation, where the user can read it and begin
   asking questions / spotting gaps, with the option to save a Markdown report
   of the condensed synthesis for later.

If a user can run this once and walk away with the full one-hop context of a
ticket in clean Markdown, the product worked.

### Secondary

- A **technical research helper** skill: takes the assembled ticket context and
  helps the user research implementation approaches and feasibility. Nice-to-have
  and droppable.

### Guardrails

- **Read-only**: the tool must never create or modify any Jira or Confluence
  data. Strictly read access.
- **No credential leakage**: tokens/credentials must never be written into
  output files, caches, or logs.
- **Graceful degradation**: if a linked ticket or referenced page is
  inaccessible, forbidden, or deleted, the run continues and reports the gap
  rather than crashing.

## User Stories

### US-01: Assemble one-hop ticket context

- **Given** a Jira ticket key for a ticket I need to prepare for,
- **When** I run the one-hop assembly,
- **Then** the skill fetches the target ticket, extracts the Jira keys and
  Confluence links it references, dispatches a subagent per linked ticket/page
  to fetch and condense it from the target ticket's perspective, and gives me
  the assembled context loaded into the conversation as a high-level summary —
  along with a note of any links it could not retrieve — with the option to
  keep chatting or save a detailed (condensed) report to a Markdown file.

#### Acceptance Criteria

- The target ticket's title, description, and comments are fetched in full and
  converted to Markdown.
- Every directly-linked Jira ticket and directly-referenced Confluence page (one
  hop only) is fetched via the retrieval primitives and condensed by a subagent
  focused on relevance to the target ticket — not echoed raw.
- The assembled findings (condensed per-item notes + gaps) land in the Claude
  conversation as part of the same run; the user is offered a save-to-Markdown
  follow-up producing the condensed synthesis as a file.
- Any link that could not be retrieved (inaccessible, forbidden, deleted) is
  reported as a gap rather than causing the run to fail.

## Functional Requirements

Design note: the system is a set of **composable** skills/tools. Retrieval is
split into single-item primitives plus a link extractor; "following links" is an
assembly step that composes them. One-hop vs. multi-hop is just how many times
the extract→fetch loop runs, so deeper traversal is cheap to add later.

The CLI primitives (FR-001–FR-004) are scaffolding, not the product surface —
they stay mechanical and deterministic. Composition (FR-005–FR-008) happens one
layer up, inside a Claude skill that orchestrates the primitives via subagents;
that is also where the system's only reasoning/synthesis step lives (see
Business Logic).

### Retrieval primitives

- FR-001: User can fetch a single Jira ticket by key (title, description,
  comments) and get it as Markdown. Priority: must-have
  > Socrates: Challenge ("comments bloat context" / "acli already shows it")
  > considered. Resolution: stands as written — clean Markdown of the full
  > ticket incl. comments is exactly the value.
- FR-002: User can fetch a single Confluence page by ID/URL and get it as
  Markdown. Priority: must-have
  > Socrates: Challenge ("pages can be huge" / "macros won't convert")
  > considered. Resolution: stands as written — whole-page Markdown is the right
  > unit for v1. (Macro-fidelity gap tracked in NFRs / Open Questions.)
- FR-003: The tool converts Atlassian rich content (ADF) into readable Markdown
  (basic formatting: headings, lists, links, code blocks). Priority: must-have
  > Socrates: Challenge ("basic fidelity misleads" / "just pass raw ADF")
  > considered. Resolution: stands as written — basic Markdown is the right
  > readability tradeoff for v1; conversion fidelity captured as an NFR.

### Link extraction

- FR-004: User can extract all Jira ticket keys and Confluence links from a
  given Markdown/ADF document. Priority: must-have
  > Socrates: Counter-argument accepted — pure link extraction MISSES prose
  > references ("see the auth epic") that have no real link. Resolution: kept as
  > written for v1 (explicit keys/links only); prose-mention detection is an
  > acknowledged limitation deferred to v2 (see Open Questions).

### Assembly (composition)

- FR-005: User can assemble one-hop context for a ticket via a Claude skill:
  fetch the target ticket in full, extract its links, then dispatch one
  subagent per directly-linked ticket and referenced Confluence page. Each
  subagent fetches its item through the retrieval primitives (FR-001/FR-002)
  and returns condensed findings framed from the target ticket's perspective
  (why it's relevant, key facts, open questions/risks) — it does not echo the
  item's raw content back into the main conversation. Priority: must-have
  > Socrates: Challenge ("one hop can flood" / "link types vary in value")
  > considered. Resolution: stands as written for *which* links to follow —
  > fetch everything one hop out, unfiltered; no link is dropped before
  > fetching. What changed from v1's original framing is *how* each fetched
  > item is surfaced: per-item subagent condensation, not a raw dump. Link-type
  > weighting/dropping remains a v2 concern (Non-Goals).

### Output

- FR-006: User can have the assembled context saved to a Markdown file on
  disk. The saved artifact is the condensed synthesis produced by FR-005
  (organized by linked item, plus a gaps section per FR-008) — not a raw
  one-hop corpus dump. Priority: must-have
  > Socrates: Counter-argument accepted — saved files go STALE against
  > Atlassian. Resolution: kept; mitigate by stamping the output file with the
  > target ticket's key and fetch timestamp so staleness is visible at a
  > glance.
- FR-007: User has the assembled context loaded into the Claude conversation
  for analysis, as the default outcome of running the FR-005 skill — the
  target ticket's full content plus each subagent's condensed findings land in
  the main agent's context as part of assembly itself, with FR-006's file save
  offered afterward as a follow-up action rather than a separate consumption
  path. Priority: must-have
  > Socrates: Challenge ("may exceed context window" / "redundant with
  > FR-006") considered. Resolution: superseded — subagent condensation (see
  > FR-005) is the chosen mitigation for context-window overflow (was Open
  > Question #3, now resolved); live loading and file save are two exit paths
  > of one skill run, not two separately-built consumption modes.
- FR-008: User receives a report of what was assembled and what was skipped
  (inaccessible/forbidden/deleted links). This falls out of FR-005 directly —
  a subagent whose fetch fails reports the gap instead of guessing content, and
  gaps are collected into the summary/report alongside the condensed findings.
  Priority: nice-to-have
  > Socrates: "Promote to must-have?" considered. Resolution: stays nice-to-have
  > in priority label, though the skill-orchestrated design now produces it as
  > a natural byproduct of FR-005's graceful-degradation requirement rather
  > than needing dedicated build effort.

### Research assist

- FR-009: User can invoke a research helper that uses the assembled context to
  explore implementation approaches and feasibility. Priority: nice-to-have
  > Socrates: Counter-argument accepted — this is largely GENERIC LLM capability
  > (Claude can already research with context loaded). Resolution: stays
  > nice-to-have; value is a curated prompt/workflow, not new mechanism.
  > Strong v2 / droppable candidate.

## Non-Functional Requirements

- **Conversion completeness — best-effort (v1)**: ADF→Markdown converts the
  common cases (headings, lists, links, code blocks, plain text). v1 makes **no
  guarantee** that every element survives; unsupported macros/panels/embeds may
  be dropped. This is an accepted v1 tradeoff given the timeline; fidelity is the
  primary intended growth area (see Open Questions).
- **Human- and agent-readable output**: the produced Markdown must render cleanly
  for a human reader and parse reliably for an LLM — readability is a target, not
  incidental.
- **Deterministic / re-runnable (retrieval primitives only)**: re-running
  FR-001–FR-004 (`fetch-ticket`, `fetch-page`, `extract-links`) on the same
  source data yields the same Markdown structure and ordering — no random
  ordering or flaky output. This does **not** extend to the FR-005 assembly
  skill's condensed output: subagent synthesis is LLM-authored and is not
  required to be byte-reproducible run-to-run, only faithful to the
  underlying (deterministic) primitive output it's condensing.
- **Read-only** *(also a guardrail)*: no writes to Atlassian, ever.
- **No credential leakage** *(also a guardrail)*: credentials never appear in
  output files, caches, or logs.
- **Graceful degradation** *(also a guardrail)*: inaccessible/forbidden/deleted
  links are reported, not fatal.

## Business Logic

**Core rule**: Given heterogeneous Atlassian content (Jira tickets and Confluence
pages, each in the ADF rich-content format), the tool normalizes it into a single
uniform, readable Markdown corpus — making scattered, differently-shaped source
content directly consumable by a human and an LLM.

Normalization is the primary value and the headline decision. A supporting rule
defines *what* gets normalized: the **context boundary** — a ticket's relevant
context is the ticket itself plus everything exactly one link-hop away
(directly-linked tickets and directly-referenced Confluence pages). This bounded
closure is what the assembly step (FR-005) applies; it is deliberately shallow in
v1 and is treated as plumbing in service of the normalization output, not the
headline feature.

The "intelligence" of understanding, gap-spotting, and research lives downstream
of the retrieval primitives (FR-001–FR-004): those stay mechanical converters,
never judging or filtering content, so the corpus they produce stays trustworthy
and reproducible. Reasoning enters one layer up, in the FR-005 assembly skill —
per-item subagents condense each linked ticket/page from the target ticket's
perspective before it reaches the main conversation. That skill still fetches
every one-hop item unfiltered (no link is skipped or weighted by type); it
changes *how* each fetched item is surfaced, not *which* items get fetched.

## Access Control

Single-user, local tool. No app-level authentication, accounts, or roles. The
tool reads only data the operator already has permission to see in Atlassian,
acting under the operator's own credentials. Strictly read-only.

The concrete authentication mechanism is a downstream concern — it depends on
which retrieval approach is chosen — and is deferred to the tech-stack step
rather than fixed here.

## Non-Goals

- **No writing to Atlassian** — the tool never creates or edits tickets,
  comments, or pages. Strictly read-only. (Locks the stated scope and the
  read-only guardrail.)
- **No multi-hop / recursive crawling** — v1 follows links exactly one hop; no
  link-of-a-link traversal. Keeps the build weekend-sized; multi-hop is v2.
- **No relevance filtering or ranking** — v1 does not judge *which* linked items
  to fetch; every one-hop item is fetched regardless of link type, and none is
  dropped or weighted. (Per-item *condensation* of what each fetched item
  contains, from the target ticket's perspective, is in scope per FR-005 — that
  is summarizing content, not deciding which links to follow.) Link-type
  weighting/ranking is a v2 concern.
- **No GUI / web app** — terminal commands plus Claude skills only; no browser or
  desktop UI for v1.

## Open Questions

1. **Prose references without explicit links** — references like "see the auth
   epic" that have no real link are NOT captured by FR-004's link extraction.
   Owner: user. Deferred to v2 (could be addressed with fuzzy key detection or an
   LLM pass).
2. **Macro/panel/embed fidelity** — Confluence macros/panels/embeds may be
   dropped by basic ADF→Markdown conversion. Acceptable for v1, but fidelity gaps
   should be made visible to the user. Owner: user. Resolution: v2 growth area.
3. **Context-window overflow** — ~~large assembled context may exceed Claude's
   context window when loaded live (FR-007). How to chunk/summarize/select when
   it does is unresolved.~~ **Resolved**: FR-005's per-item subagent
   condensation is the chosen mitigation — each linked ticket/page is
   summarized from the target ticket's perspective by its own subagent before
   returning to the main conversation, so only condensed findings (not raw
   fetched content) accumulate in the main context.
4. **Link relevance filtering** — link-type weighting and dropping low-signal
   "relates to" links is deferred to v2; v1 fetches everything one hop out.
   Owner: user. Deferred to v2.
