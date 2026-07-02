---
project: Jira & Confluence Context Skills
version: 1
status: draft
created: 2026-07-01
updated: 2026-07-02
prd_version: 1
main_goal: low-complexity
top_blocker: capacity
---

# Roadmap: Jira & Confluence Context Skills

> Derived from `context/foundation/prd.md` (v1) + auto-researched codebase baseline.
> Edit-in-place; archive when superseded.
> Slices below are listed in dependency order. The "At a glance" table is the index.

## Vision recap

Engineers spend heavy, cognitively draining time reconstructing a ticket's
scattered context (the ticket, its linked tickets, comments, and referenced
Confluence pages) before planning or design meetings. The bet here is that once
that scattered context is *assembled* into one clean, readable Markdown corpus,
an LLM can do most of the remaining synthesis, gap-spotting, and research work —
so the tool's only job is to produce that trustworthy corpus, not to do the
reasoning itself.

## North star

**S-04: User can assemble one-hop context for a ticket, written to Markdown
files** — this is the PRD's Primary Success Criterion verbatim ("run this once
and walk away with the full one-hop context of a ticket in clean Markdown"): the
smallest end-to-end slice that proves assembling scattered context is actually
valuable.

> The **north star** here means: the smallest end-to-end slice whose successful
> delivery would prove the core product hypothesis. It's placed as early as its
> Prerequisites allow, because every other slice only matters if this one works.

## At a glance

| ID   | Change ID                     | Outcome (user can …)                                              | Prerequisites   | PRD refs             | Status   |
| ---- | ------------------------------ | ------------------------------------------------------------------ | --------------- | --------------------- | -------- |
| F-01 | atlassian-readonly-auth        | (foundation) read-only Jira + Confluence auth is wired             | —                | Access Control, NFR   | ready    |
| S-01 | fetch-jira-ticket              | fetch a single Jira ticket by key as clean Markdown                | F-01             | FR-001, FR-003, US-01 | proposed |
| S-02 | fetch-confluence-page          | fetch a single Confluence page by ID/URL as clean Markdown         | F-01             | FR-002, FR-003, US-01 | proposed |
| S-03 | extract-ticket-links           | extract Jira keys and Confluence links from a document             | —                | FR-004, US-01         | ready    |
| S-04 | assemble-one-hop-context       | assemble one-hop ticket context to Markdown file(s), gaps reported | S-01, S-02, S-03 | FR-005, FR-006, FR-008, US-01 | proposed |
| S-05 | load-context-into-claude       | load the assembled one-hop context into a Claude conversation      | S-04             | FR-007, US-01         | proposed |
| S-06 | extract-ticket-hierarchy       | see a ticket's parent and child work items alongside its links     | S-03             | — (not yet in PRD)    | proposed |

## Streams

Navigation aid — groups items that share a Prerequisites chain. Canonical ordering still lives in the dependency graph below; this table is the proposed reading order across parallel tracks.

| Stream | Theme                | Chain                     | Note                                                                                   |
| ------ | --------------------- | -------------------------- | --------------------------------------------------------------------------------------- |
| A      | Retrieval primitives  | `F-01` → `S-01` / `S-02`   | Both fetch primitives are auth-gated and independent of each other — build in parallel. |
| B      | Link extraction       | `S-03` → `S-06`            | No foundation prerequisite; pure parsing utility, buildable and testable in isolation. `S-06` extends `S-03`'s result shape. |
| C      | Assembly & delivery   | `S-04` → `S-05`            | Joins Stream A at `S-01`/`S-02` and Stream B at `S-03`; this is the north star chain.    |

## Baseline

What's already in place in the codebase as of `2026-07-01` (auto-researched, user-confirmed).
Foundations below assume these are present and do NOT re-scaffold them.

- **Frontend:** absent — not applicable; CLI-only product (Non-Goals: "No GUI / web app").
- **Backend / API:** partial — Typer CLI scaffold exists with only a `version` command (`src/jira_tools/cli.py:10`); no `fetch-ticket`/`fetch-page`/`assemble` commands yet.
- **Data:** absent — no Atlassian retrieval library installed (`pyproject.toml` lists only `pydantic` + `typer`), no ADF pydantic models, no link-extraction code.
- **Auth:** absent — mechanism explicitly left open in `tech-stack.md` ("decide once the retrieval tool/library is chosen"); no credential-handling code exists.
- **Deploy / infra:** partial — `ci_provider: github-actions` declared per `tech-stack.md`, but no `.github/workflows/` present yet.
- **Observability:** absent — no logging/error-reporting code, and no established pattern yet for keeping credentials out of logs (an NFR).

## Foundations

### F-01: Read-only Atlassian auth wired

- **Outcome:** (foundation) the CLI can authenticate to Jira and Confluence read-only, under the operator's own credentials, with the chosen mechanism never writing tokens to output, cache, or logs.
- **Change ID:** atlassian-readonly-auth
- **PRD refs:** Access Control, NFR "Read-only", NFR "No credential leakage"
- **Unlocks:** S-01, S-02 (both fetch primitives need a working, credential-safe connection before they can hit real Atlassian data)
- **Prerequisites:** external state — operator already has a valid Jira + Confluence account with read access (per PRD's Access Control section)
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:**
  - Auth mechanism choice — reuse `acli`'s existing login session vs. an Atlassian API token for the Python library. Owner: user. Block: no (an implementation decision `/10x-plan` can resolve when planning this foundation; tech-stack.md already frames both options).
- **Risk:** every downstream slice depends on this being both read-only and leak-proof — get the credential-safety contract right here once, rather than re-verifying it per fetch primitive.
- **Status:** ready

## Slices

### S-01: Fetch a single Jira ticket to Markdown

- **Outcome:** user can fetch a single Jira ticket by key and get its title, description, and comments as clean Markdown.
- **Change ID:** fetch-jira-ticket
- **PRD refs:** FR-001, FR-003, US-01
- **Prerequisites:** F-01
- **Parallel with:** S-02, S-03
- **Blockers:** —
- **Unknowns:** —
- **Risk:** the ADF→Markdown conversion built here is shared with S-02 — comments are the trickiest content to convert faithfully, but v1 accepts best-effort fidelity per the Conversion Completeness NFR, so this isn't a gate to ship.
- **Status:** proposed

### S-02: Fetch a single Confluence page to Markdown

- **Outcome:** user can fetch a single Confluence page by ID/URL and get it as clean Markdown.
- **Change ID:** fetch-confluence-page
- **PRD refs:** FR-002, FR-003, US-01
- **Prerequisites:** F-01
- **Parallel with:** S-01, S-03
- **Blockers:** —
- **Unknowns:**
  - Macro/panel/embed fidelity — basic ADF→Markdown conversion may silently drop Confluence macros/panels/embeds. Owner: user. Block: no (accepted v1 tradeoff per NFR; PRD Open Question #2 tracks it for v2).
- **Risk:** dropped macros should stay visible as a gap rather than silently vanish — worth a "some content may be simplified" note in output, not worth building macro-fidelity now.
- **Status:** proposed

### S-03: Extract ticket links from a document

- **Outcome:** user can extract all Jira ticket keys and Confluence links referenced in a given Markdown/ADF document.
- **Change ID:** extract-ticket-links
- **PRD refs:** FR-004, US-01
- **Prerequisites:** —
- **Parallel with:** S-01, S-02
- **Blockers:** —
- **Unknowns:**
  - Prose-only references (e.g. "see the auth epic") with no explicit link are not captured by explicit-link extraction. Owner: user. Block: no (PRD explicitly defers fuzzy/prose detection to v2; Open Question #1).
- **Risk:** missing prose-only mentions is an accepted v1 gap, not a defect — building fuzzy detection now would spend scarce after-hours capacity on a nice-to-have.
- **Status:** ready

### S-04: Assemble one-hop context to Markdown files

- **Outcome:** user can assemble one-hop context for a ticket — fetch the target, extract its links, fetch every directly-linked ticket and referenced Confluence page, convert everything to Markdown, and get it written to Markdown file(s) on disk, with any inaccessible/forbidden/deleted links reported rather than failing the run.
- **Change ID:** assemble-one-hop-context
- **PRD refs:** FR-005, FR-006, FR-008, US-01
- **Prerequisites:** S-01, S-02, S-03
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:**
  - Link-relevance filtering (weighting link types, dropping low-signal "relates to" links) is out of scope here. Owner: user. Block: no (PRD explicitly defers to v2; Open Question #4 — v1 fetches everything one hop out).
- **Risk:** this is the slice that actually proves the core hypothesis — treating an inaccessible/forbidden/deleted link as a reported gap rather than a crash (the graceful-degradation guardrail) matters as much as the happy path.
- **Status:** proposed

### S-05: Load assembled context into a Claude conversation

- **Outcome:** user can load the assembled one-hop context directly into a Claude conversation for analysis and Q&A, as an alternative (or complement) to reading the Markdown files.
- **Change ID:** load-context-into-claude
- **PRD refs:** FR-007, US-01
- **Prerequisites:** S-04
- **Parallel with:** —
- **Blockers:** —
- **Unknowns:**
  - Context-window overflow — a large assembled corpus may exceed Claude's context window with no chunking/summarization strategy decided. Owner: user. Block: no (PRD defers this; ship the simplest "load it all" version first and let real usage show whether truncation is actually needed — Open Question #3).
- **Risk:** don't over-build a chunking scheme speculatively — the capacity budget is scarce and this NFR gap is explicitly deferred in the PRD.
- **Status:** proposed

### S-06: Extract ticket hierarchy (parent + child work items)

- **Outcome:** user can see a ticket's parent ticket and child work items alongside the Jira keys, issue links, and Confluence pages `extract-ticket-links` (S-03) already surfaces.
- **Change ID:** extract-ticket-hierarchy (not yet created)
- **PRD refs:** — not yet covered by the PRD; raised directly by the user after S-03 shipped. Needs a PRD update (new FR) before this is plannable.
- **Prerequisites:** S-03 (extends its result shape)
- **Parallel with:** S-04, S-05 (once unblocked)
- **Blockers:** scope decision below
- **Unknowns:**
  - Scope of "child work items" — `fields.subtasks` is inline on the issue response, same shape as `fields.parent`/`fields.issuelinks` (no extra API call, a pure additive fetch). Epic children, by contrast, are *not* inlined on the issue and would need a separate JQL search call per ticket — a materially bigger change (extra network round-trip, still read-only). Owner: user. Block: yes — this must be resolved before `/10x-plan` can scope the change.
- **Risk:** if scope includes Epic children, this stops being a "free" additive fetch like `issuelinks` and becomes a second network call per ticket — worth resolving the scope question first rather than discovering it mid-plan.
- **Status:** proposed

## Backlog Handoff

| Roadmap ID | Change ID               | Suggested issue title                                          | Ready for `/10x-plan` | Notes                                    |
| ---------- | ------------------------ | ---------------------------------------------------------------- | ---------------------- | ------------------------------------------ |
| F-01       | atlassian-readonly-auth  | Wire read-only Atlassian auth (Jira + Confluence)                 | yes                    | Run `/10x-plan atlassian-readonly-auth`  |
| S-01       | fetch-jira-ticket        | Fetch a single Jira ticket as Markdown                            | no                     | Blocked on F-01                          |
| S-02       | fetch-confluence-page    | Fetch a single Confluence page as Markdown                        | no                     | Blocked on F-01                          |
| S-03       | extract-ticket-links     | Extract Jira keys / Confluence links from a document              | yes                    | Run `/10x-plan extract-ticket-links`     |
| S-04       | assemble-one-hop-context | Assemble one-hop ticket context to Markdown files                 | no                     | Blocked on S-01, S-02, S-03 (north star)  |
| S-05       | load-context-into-claude | Load assembled context into a Claude conversation                 | no                     | Blocked on S-04                          |
| S-06       | extract-ticket-hierarchy | Extract a ticket's parent + child work items                      | no                     | Blocked on scope decision (subtasks-only vs. + Epic children) and a PRD update |

## Open Roadmap Questions

1. **Prose references without explicit links** ("see the auth epic") are not captured by FR-004's explicit-link extraction. Owner: user. Block: S-03 (not blocking — deferred to v2).
2. **Macro/panel/embed fidelity** — Confluence macros/panels/embeds may be dropped by basic ADF→Markdown conversion. Owner: user. Block: S-02 (not blocking — accepted v1 tradeoff; fidelity gap should stay visible to the user).
3. **Context-window overflow** — large assembled context may exceed Claude's context window when loaded live. Owner: user. Block: S-05 (not blocking — deferred; chunking strategy unresolved).
4. **Link relevance filtering** — link-type weighting / dropping low-signal "relates to" links is out of scope for v1. Owner: user. Block: S-04 (not blocking — deferred to v2).
5. **Ticket hierarchy scope** — should S-06 cover subtasks only (inline on the issue, free) or also Epic children (needs a separate JQL search call per ticket)? Owner: user. Block: S-06 (blocking — must be resolved before `/10x-plan extract-ticket-hierarchy`).

## Parked

- **Research helper skill (FR-009)** — Why parked: PRD marks it nice-to-have/droppable, and its own Socrates note calls it "largely generic LLM capability" rather than new mechanism. Combined with `main_goal: low-complexity` and the `capacity` blocker, it's deferred past the must-have path (F-01, S-01–S-05) rather than roadmapped as its own slice.
- **No writing to Atlassian** — Why parked: locks the PRD's stated scope and the read-only guardrail; strictly out of scope, not a v2 candidate.
- **No multi-hop / recursive crawling** — Why parked: v1 follows links exactly one hop; keeps the build weekend-sized. Multi-hop is a v2 concern.
- **No relevance filtering or ranking** — Why parked: v1 fetches all one-hop items unfiltered and lets the human/LLM judge relevance. Scoring is a v2 concern.
- **No GUI / web app** — Why parked: terminal commands plus Claude skills only for v1; no browser or desktop UI.

## Done

