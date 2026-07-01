---
project: Jira & Confluence Context Skills
context_type: greenfield
updated: 2026-06-23
checkpoint:
  current_phase: 8
  phases_completed: [1, 2, 3, 4, 5, 6, 7]
  frs_drafted: 9
  quality_check_status: accepted
product_type: cli
target_scale:
  users: small
timeline_budget:
  mvp_weeks: 1
  hard_deadline: null
  after_hours_only: true
---

<!-- Shaping in progress. Sections are written phase-by-phase by /10x-shape. -->

## Vision & Problem Statement

Software engineers and architects spend large amounts of focused time
understanding a Jira ticket and preparing for planning, refinement, and design
meetings. The context needed is scattered across the ticket itself, its linked
tickets, comments, and related Confluence pages, so prep is a slow, manual,
cognitively heavy reconstruction job.

The product is a set of Claude skills/tools that retrieve and assemble this
scattered context, then use an LLM to accelerate four kinds of work that are
currently done by hand:

- **Context gathering** — collecting ticket + linked tickets + comments +
  Confluence pages into one place.
- **Synthesis / understanding** — making sense of what is actually being asked
  and what matters.
- **Gap & risk spotting** — surfacing what is missing, ambiguous, or risky
  before the meeting.
- **Technical research** — exploring implementation approaches and feasibility.

**Insight**: the bottleneck is human synthesis of dispersed context. Once that
context is *assembled* into a clean, readable form, an LLM can do much of the
understanding and prep work that currently consumes an engineer's focus.

## User & Persona

**Primary persona** — Individual engineer / architect preparing solo.
An IC (including the author) who needs the full picture of a ticket before a
meeting. Works on their own machine, for their own understanding. The assembled
context is consumed two ways, equally: persisted as Markdown files (readable and
searchable by both human and agent) and loaded live into a Claude conversation
for immediate analysis and Q&A.

## Access Control

Single-user, local tool. No app-level authentication, accounts, or roles. The
tool reads only data the operator already has permission to see in Atlassian,
acting under the operator's own credentials.

The concrete authentication mechanism (reuse `acli`'s existing login vs. an
Atlassian API token for the Python library) is deferred to the tech-stack step
and depends on which retrieval tool/library is chosen. See
`## Forward: tech-stack`.

## Success Criteria

### Primary

The end-to-end multi-source assembly flow works for a single ticket:

1. The user supplies a Jira ticket key.
2. The tool fetches that ticket (title, description, comments).
3. It fetches every ticket **directly linked** to the target (one hop, no
   recursion) and every Confluence page **directly referenced/linked** from the
   target ticket.
4. All fetched content is converted from Atlassian's JSON format (ADF) to
   readable Markdown.
5. The assembled context is written to Markdown file(s) and/or loaded into a
   Claude conversation, where the user can read it and begin asking questions /
   spotting gaps.

If a user can run this once and walk away with the full one-hop context of a
ticket in clean Markdown, the product worked.

### Secondary (nice-to-have, droppable)

- A **technical research helper** skill: takes the assembled ticket context and
  helps the user research implementation approaches and feasibility.

### Guardrails (must not break)

- **Read-only**: the tool must never create or modify any Jira or Confluence
  data. Strictly read access.
- **No credential leakage**: tokens/credentials must never be written into
  output files, caches, or logs.
- **Graceful degradation**: if a linked ticket or referenced page is
  inaccessible, forbidden, or deleted, the run continues and reports the gap
  rather than crashing.

## Functional Requirements

Design note: the system is a set of **composable** skills/tools. Retrieval is
split into single-item primitives plus a link extractor; "following links" is an
assembly step that composes them. One-hop vs. multi-hop is just how many times
the extract→fetch loop runs, so deeper traversal is cheap to add later.

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
- FR-003: The tool converts Atlassian rich content (ADF JSON) into readable
  Markdown (basic formatting: headings, lists, links, code blocks).
  Priority: must-have
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

- FR-005: User can assemble one-hop context for a ticket: fetch the target,
  extract its links, then fetch each directly-linked ticket and referenced
  Confluence page. Priority: must-have
  > Socrates: Challenge ("one hop can flood" / "link types vary in value")
  > considered. Resolution: stands as written — fetch everything one hop out;
  > the human/LLM filters afterward. Relevance filtering is a v2 concern.

### Output

- FR-006: User can have the assembled context written to Markdown file(s) on
  disk. Priority: must-have
  > Socrates: Counter-argument accepted — saved files go STALE against
  > Atlassian. Resolution: kept; mitigate by stamping each output file with its
  > source key/ID and fetch timestamp so staleness is visible at a glance.
- FR-007: User can load the assembled context into a Claude conversation for
  analysis. Priority: must-have
  > Socrates: Challenge ("may exceed context window" / "redundant with FR-006")
  > considered. Resolution: stands as written — live loading is a distinct
  > consumption mode. Context-size handling noted as an NFR/Open Question.
- FR-008: User receives a report of what was assembled and what was skipped
  (inaccessible/forbidden/deleted links). Priority: nice-to-have
  > Socrates: "Promote to must-have?" considered. Resolution: stays nice-to-have
  > — v1 can ship without it and add once retrieval is solid.

### Research assist

- FR-009: User can invoke a research helper that uses the assembled context to
  explore implementation approaches and feasibility. Priority: nice-to-have
  > Socrates: Counter-argument accepted — this is largely GENERIC LLM capability
  > (Claude can already research with context loaded). Resolution: stays
  > nice-to-have; value is a curated prompt/workflow, not new mechanism.
  > Strong v2 / droppable candidate.

## Business Logic

**Core rule**: Given heterogeneous Atlassian content (Jira tickets and Confluence
pages, each in ADF JSON), the tool normalizes it into a single uniform, readable
Markdown corpus — making scattered, differently-shaped source content directly
consumable by a human and an LLM.

Normalization is the primary value/decision. A supporting rule defines *what*
gets normalized: the **context boundary** — a ticket's relevant context is the
ticket itself plus everything exactly one link-hop away (directly-linked tickets
and directly-referenced Confluence pages). This bounded closure is what the
assembly step (FR-005) applies; it is deliberately shallow in v1 and is treated
as plumbing in service of the normalization output, not the headline feature.

The "intelligence" of understanding/gap-spotting/research lives downstream in the
LLM consuming this corpus — the tool's job is to produce a clean, trustworthy
corpus for it to reason over.

## Non-Functional Requirements

- **Conversion completeness — best-effort (v1)**: ADF→Markdown converts the
  common cases (headings, lists, links, code blocks, plain text). v1 makes **no
  guarantee** that every element survives; unsupported macros/panels/embeds may
  be dropped. This is an accepted v1 tradeoff given the timeline; fidelity is the
  primary intended growth area (see Open Questions).
- **Human- and agent-readable output**: the produced Markdown must render cleanly
  for a human reader and parse reliably for an LLM — readability is a target, not
  incidental.
- **Deterministic / re-runnable**: re-running assembly on the same ticket yields
  the same Markdown structure and ordering (modulo changes in the source data) —
  no random ordering or flaky output.
- **Read-only** *(also a guardrail)*: no writes to Atlassian, ever.
- **No credential leakage** *(also a guardrail)*: credentials never appear in
  output files, caches, or logs.
- **Graceful degradation** *(also a guardrail)*: inaccessible/forbidden/deleted
  links are reported, not fatal.

## User Stories

### US-01: Assemble one-hop ticket context

**Given** a Jira ticket key for a ticket I need to prepare for,
**When** I run the one-hop assembly,
**Then** the tool fetches the target ticket, extracts the Jira keys and
Confluence links it references, fetches each of those linked tickets and pages,
converts everything from ADF to readable Markdown, and gives me the assembled
context as Markdown file(s) and/or loaded into Claude — along with a note of any
links it could not retrieve.

## Quality cross-check

All elements present — status: accepted. No gaps recorded.

- Access Control: present (single-user, local, read-only).
- Business Logic: present (one-sentence normalization rule).
- Project artifacts: present (this file, valid checkpoint).
- Timeline-cost ack: present (mvp_weeks: 1, ≤ 3 — no acknowledgment required).
- Non-Goals: present (4 entries).

The four Open Questions are intentional v2 deferrals, not quality gaps.

## Non-Goals

- **No writing to Atlassian** — the tool never creates or edits tickets,
  comments, or pages. Strictly read-only. (Locks the seed's stated scope and the
  read-only guardrail.)
- **No multi-hop / recursive crawling** — v1 follows links exactly one hop; no
  link-of-a-link traversal. Keeps the build weekend-sized; multi-hop is v2.
- **No relevance filtering or ranking** — v1 does not judge which linked items
  matter; it fetches all one-hop items and lets the human/LLM filter. Relevance
  scoring is a v2 concern.
- **No GUI / web app** — terminal commands plus Claude skills only; no browser or
  desktop UI for v1.

## Open Questions

- Prose references to tickets/pages (e.g. "see the auth epic") that have no
  explicit link are NOT captured by FR-004's link extraction. Deferred to v2 —
  could be addressed with fuzzy key detection or an LLM pass.
- Confluence macros/panels/embeds may be dropped by basic ADF→Markdown
  conversion; acceptable for v1, but fidelity gaps should be visible to the user.
- Large assembled context may exceed Claude's context window (FR-007). How to
  chunk/summarize/select when it does — deferred.
- Link relevance filtering (link-type weighting, dropping low-signal "relates
  to" links) deferred to v2; v1 fetches everything one hop out.

## Forward: tech-stack

Captured from the seed idea (informational — NOT part of the PRD; the tech-stack
step downstream of /10x-prd consumes this):

- Data retrieval: official Atlassian `acli` CLI tool.
- Alternative: Atlassian Python API (https://atlassian-python-api.readthedocs.io/).
- Atlassian stores rich content in a JSON-based format (ADF) that must be
  converted to Markdown for human + agent readability. Only basic formatting
  support needed initially.
- Language preference: Python first, then JS/TS. Target Ubuntu first (matches the
  team's typical setup).
- **Auth mechanism (open)**: reuse `acli`'s existing login session vs. an
  Atlassian API token supplied to the Python library. Decide once the retrieval
  tool/library is chosen — the auth approach should match it.
