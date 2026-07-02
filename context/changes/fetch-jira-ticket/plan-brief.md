# Fetch a Single Jira Ticket as Markdown — Plan Brief

> Full plan: `context/changes/fetch-jira-ticket/plan.md`
> Research: `context/changes/fetch-jira-ticket/research.md`

## What & Why

Add a `fetch-ticket <KEY>` CLI command that fetches a Jira ticket's title,
description, and comments and prints them as clean Markdown. This is
roadmap slice S-01 — the first of the two independent retrieval primitives
(FR-001) that the later one-hop assembly slice (S-04, the product's north
star) will compose together.

## Starting Point

The CLI currently has only `version` and `auth-check`. `ReadOnlyJiraClient`
exposes exactly one method (`whoami`) and no ticket-fetching capability
exists. No ADF conversion module or ticket/comment models exist yet.

## Desired End State

Running `jira-tools fetch-ticket PROJ-123` against a real ticket prints one
Markdown document to stdout: a title, a metadata line (key/status/type), a
`## Description` section, and a `## Comments` section with one dated,
attributed subsection per comment. Fetch failures (not found / no access)
print a clean stderr message and exit non-zero — no stack traces, no
credentials ever in output.

## Key Decisions Made

| Decision                         | Choice                                          | Why (1 sentence)                                                                 | Source   |
| --------------------------------- | ------------------------------------------------ | --------------------------------------------------------------------------------- | -------- |
| ADF→Markdown library              | `marklas` only, no fallback code                  | Research's hands-on smoke test found no functional gap; native mypy --strict compliance, one dependency. | Research |
| Output destination                | stdout only                                       | Matches Unix CLI conventions and the existing `auth-check` style; file output (FR-006) is S-04's job.     | Plan     |
| Comment formatting                | `### Comment by <author> (<date>)` heading + body | Readable, scannable, keeps discussion-thread context (who said what).            | Plan     |
| Metadata scope                    | Title + one-line status/type/key subtitle         | Makes standalone output self-identifying at near-zero cost.                       | Plan     |
| Fetch-failure handling            | stderr message + exit 1, no exception propagation | Matches "degrade gracefully, don't crash" guardrail while keeping a single-item primitive's contract simple (succeed or fail clearly). | Plan     |
| Comment pagination                | Paginate through all comments                     | `issue_get_comments()` only returns one page; user chose completeness over the simpler single-page default. | Plan     |

## Scope

**In scope:**
- `fetch-ticket <KEY>` command
- ADF→Markdown conversion module (`adf.py`, wrapping `marklas`)
- Jira ticket + comment retrieval, with full comment pagination
- Markdown document assembly (title, metadata, description, comments)
- Error handling for not-found/forbidden tickets

**Out of scope:**
- Confluence page fetching (S-02), link extraction (S-03), one-hop assembly
  (S-04), file output (FR-006), Claude-conversation loading (FR-007),
  gap/skip reporting (FR-008)
- Any ADF library fallback (`atlas-doc-parser` or otherwise)
- Prose/fuzzy reference detection, timestamp reformatting

## Architecture / Approach

Three layers, each independently testable: `adf.py` converts a single ADF
node tree to a Markdown fragment (no Jira knowledge); `atlassian_client.py`
gains `get_ticket()` returning a typed `JiraTicket` (fetches fields +
paginates all comments, no Markdown knowledge); `ticket_document.py` +
`cli.py` assemble the final document and wire up the command. Raw ADF JSON
is parsed into the `ADFNode` pydantic model at the API boundary and only
turned back into a dict at the single point where `marklas.to_md()` is
called, per CLAUDE.md's "pydantic models at the ADF boundary" rule.

## Phases at a Glance

| Phase                                    | What it delivers                                              | Key risk                                                    |
| ------------------------------------------ | ---------------------------------------------------------------- | -------------------------------------------------------------- |
| 1. ADF→Markdown conversion module          | `adf.py` wrapping `marklas`, unit-tested against fixture ADF     | `marklas`'s actual output quality — already de-risked by research's hands-on smoke test |
| 2. Jira ticket retrieval                   | `get_ticket()` on `ReadOnlyJiraClient`, full comment pagination  | Manual pagination logic (library has no built-in support) — needs a dedicated multi-page test |
| 3. Markdown document assembly + CLI wiring | `ticket_document.py` + `fetch-ticket` command                    | Error-handling path (no credential leakage on failure) needs explicit test coverage |

**Prerequisites:** F-01 (`atlassian-readonly-auth`) already merged — read-only
auth and config loading are in place.
**Estimated effort:** ~1 session across 3 phases; small, additive slice.

## Open Risks & Assumptions

- Assumes Jira Cloud's `rest/api/2/issue` endpoint returns ADF (not wiki
  markup) for `description`/comment `body` fields — consistent with
  research.md and current Jira Cloud behavior, but not verified against the
  operator's specific site until Phase 2's manual verification step.
- `marklas`'s panel-as-raw-HTML (`<aside>`) output is accepted as-is per the
  best-effort NFR; if it proves visually jarring in practice, a
  post-processing step could be added later (not planned now).

## Success Criteria (Summary)

- `jira-tools fetch-ticket <KEY>` against a real ticket produces clean,
  correctly-ordered, correctly-attributed Markdown with all comments present
  (not just the first page).
- Fetching a nonexistent/inaccessible ticket fails cleanly (stderr + exit 1),
  never with a stack trace or leaked credential.
- Full check suite (`ruff`, `mypy --strict`, `pytest`) passes.
