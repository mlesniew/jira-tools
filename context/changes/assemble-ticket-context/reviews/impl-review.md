<!-- IMPL-REVIEW-REPORT -->
# Implementation Review: Polish the assemble-ticket-context skill

- **Plan**: context/changes/assemble-ticket-context/plan.md
- **Scope**: Phase 1 & 2 (full plan)
- **Date**: 2026-07-03
- **Verdict**: NEEDS ATTENTION
- **Findings**: 0 critical, 2 warnings, 2 observations

**Scope note**: the plan's own Progress convention says a phase counts as
"completed" only when *all* its checkboxes (Automated + Manual) are `[x]`.
Neither phase strictly qualifies — only Automated rows are ticked (see F3).
Given `change.md` already declares `status: implemented` and both phases
have landed commits (c26efef, 5d114f8), this review covered both phases in
full rather than treating scope as empty.

## Verdicts

| Dimension | Verdict |
|-----------|---------|
| Plan Adherence | PASS |
| Scope Discipline | PASS |
| Safety & Quality | WARNING |
| Architecture | PASS |
| Pattern Consistency | PASS |
| Success Criteria | WARNING |

## Findings

### F1 — Read-only guardrail is prompt-only for subagents that don't need write access

- **Severity**: WARNING
- **Impact**: 🔬 HIGH — architectural stakes; think carefully before deciding
- **Dimension**: Safety & Quality
- **Location**: `.claude/skills/assemble-ticket-context/SKILL.md:112-118, 133-135`
- **Detail**: Phase 2 switched Step 3's dispatch from `Explore` to
  `general-purpose`, trading a structural read-only guarantee for a
  prompt-level one ("must not create, write, or edit any file"). The plan's
  Key Discoveries section justifies this as matching repo convention for
  "run + synthesize" work. Checked that claim against the actual sibling
  skills cited elsewhere in the plan (`~/.claude/skills/10x-research/SKILL.md:93-94`,
  `~/.claude/skills/10x-frame/SKILL.md:144-145`): their real split is
  Explore = structural search, general-purpose = judgment/reasoning over
  what's found — not read-only-vs-write. Step 3's actual job (run one fetch
  command, read the output, return a condensed judgment) needs none of what
  `general-purpose` has that `Explore` lacks (Write, Edit, Agent, Artifact,
  ExitPlanMode, NotebookEdit) — this environment's own Explore description
  ("Fast read-only search agent... Tools: All tools except Agent, Artifact,
  ExitPlanMode, Edit, Write, NotebookEdit") already covers everything Step 3
  needs, including Bash for the fetch call. The dispatched subagents read
  ticket/Confluence-page content that isn't fully trusted (anyone with edit
  access to a linked ticket can shape its body) — prompt-injection-to-tool-misuse
  is a real, demonstrated risk pattern against LLM agents, and CLAUDE.md
  names "strictly read-only" as an explicit guardrail here, not a nice-to-have.
- **Fix A ⭐ Recommended**: Revert Step 3's dispatch to `subagent_type:
  "Explore"` and drop the now-redundant "must not create, write, or edit any
  file" sentence (enforced structurally instead).
  - Strength: Zero functional capability lost — Explore already grants
    everything Step 3 uses (Bash, Read, reasoning) — while closing the
    write/edit vector at the tool level instead of the prompt level.
  - Tradeoff: Reopens a decision already made and shipped in commit
    5d114f8; the plan's "matches repo convention" rationale rests on a
    convention that doesn't actually apply the way the plan characterized it.
  - Confidence: HIGH — verified against this environment's Explore
    tool-grant list and both cited sibling skills' actual text.
  - Blind spot: Haven't run the skill live with Explore to confirm no step
    implicitly wants a scratch file; SKILL.md's Step 3 text doesn't
    describe needing one.
- **Fix B**: Keep `general-purpose`, accept the residual risk as-is.
  - Strength: No further edit needed; keeps Phase 2 exactly as shipped.
  - Tradeoff: Leaves the read-only guarantee dependent on the subagent
    correctly resisting injected instructions in fetched content, with no
    structural backstop.
  - Confidence: MEDIUM — real-world prompt-injection-to-write incidents
    against LLM agents are documented; likelihood here is unproven either way.
  - Blind spot: No way to verify after the fact that a given run's subagent
    never attempted a write, short of reading its full transcript every time.
- **Decision**: FIXED (Fix A) — Step 3's dispatch reverted to `Explore`;
  redundant "must not create, write, or edit any file" prompt sentence
  removed (`SKILL.md:110-135`).

### F2 — Step 0 relays auth-check's raw exception text, not a fixed generic message

- **Severity**: WARNING
- **Impact**: 🔎 MEDIUM — real tradeoff; pause to reason through it
- **Dimension**: Safety & Quality
- **Location**: `.claude/skills/assemble-ticket-context/SKILL.md:41-46` ·
  `src/jira_tools/cli.py:149-153`
- **Detail**: The plan's "Critical Implementation Details" section says
  Step 0 should "surface that command's output verbatim as the stop
  reason," reasoning that all CLI fetch failures collapse into one safe
  generic message. Verified against `cli.py`: true for `fetch_ticket`,
  `fetch_page`, and `extract_links` (lines 71-73, 98-100, 130-133, 139-142
  — all fixed strings), but **not** for `auth-check`'s `_report` helper
  (line 152): `typer.echo(f"{product}: FAIL ({exc})")` embeds the raw
  stringified exception from the underlying Atlassian HTTP client.
  `ConfigError` messages are separately, deliberately safe ("messages are
  safe to print as-is" per `config.py:24`), but the credential-check branch
  isn't — it wasn't covered by the plan's own "all failures are generic"
  generalization, and CLAUDE.md names "no credentials in output/logs/cache"
  as an explicit guardrail. In practice HTTP Basic Auth exceptions rarely
  echo the credential itself, so this is a gap in the plan's stated safety
  reasoning more than a proven leak.
- **Fix A ⭐ Recommended**: Narrow Step 0's relay instruction — e.g. "relay
  the PASS/FAIL lines auth-check printed; if a FAIL reason contains more
  than a short error phrase (e.g. raw HTTP/network detail), summarize it
  rather than pasting it verbatim."
  - Strength: Closes the gap between the plan's stated assumption and
    auth-check's actual behavior without touching CLI code, which the plan
    explicitly puts out of scope.
  - Tradeoff: Natural-language instruction is soft enforcement, not the
    code-level guarantee the fetch commands get.
  - Confidence: MEDIUM — narrows exposure but can't fully guarantee it.
  - Blind spot: Haven't observed a real auth-check FAIL in this environment
    to see what today's exception text actually looks like.
- **Fix B**: Leave Step 0 as-is; accept the risk, since Basic Auth
  exceptions from `requests`/`atlassian-python-api` don't typically echo
  credentials.
  - Strength: No further edit; matches the plan's explicit "not modifying
    the CLI" scope boundary.
  - Tradeoff: The "no credentials in output" guardrail rests on an
    assumption about a third-party library's exception formatting, not
    verified code behavior — unlike every other fetch path in this file.
  - Confidence: MEDIUM — no known leak in this library, but unverified
    against the exact pinned version.
  - Blind spot: Haven't traced atlassian-python-api's exact exception
    classes on 401/403 to rule out header echoing.
- **Decision**: FIXED (Fix A) — Step 0's relay instruction narrowed to
  summarize long/raw FAIL reasons instead of pasting verbatim
  (`SKILL.md:41-48`).

### F3 — Manual Progress checkboxes unchecked despite change.md status: implemented

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Success Criteria
- **Location**: `context/changes/assemble-ticket-context/plan.md:381-383, 395-398`
- **Detail**: All 6 Manual verification items (1.3-1.5, 2.4-2.7) are still
  `- [ ]` in both phases, yet `change.md` was stamped `status: implemented`
  in the epilogue commit (ff2f37f). There's real contemporaneous evidence
  testing happened: an untracked `SICM-4025-context.md` in the repo root,
  timestamped `2026-07-03T06:36:49Z` (today), correctly rendering the
  no-relation heading form, a populated Gaps section, and condensed
  per-item findings matching Step 6's template — this looks like a real
  end-to-end run, not a fabricated sample. The checkboxes just weren't
  flipped afterward.
- **Fix**: Tick off the Manual items that are actually confirmed (2.6 looks
  directly evidenced by `SICM-4025-context.md`) and confirm the rest
  (auth-failure and PATH-not-found simulations, subagent-transcript read)
  actually happened before checking them off too.
- **Decision**: ACKNOWLEDGED, not fixed — `SICM-4025-context.md`, the
  finding's cited evidence, is no longer present on disk at triage time, so
  none of the 6 Manual checkboxes (1.3-1.5, 2.4-2.7) were ticked without a
  current, verifiable basis. Left `- [ ]` in `plan.md` pending a fresh
  end-to-end run or explicit user attestation.

### F4 — No overwrite check before saving the report

- **Severity**: OBSERVATION
- **Impact**: 🏃 LOW — quick decision; fix is obvious and narrowly scoped
- **Dimension**: Safety & Quality
- **Location**: `.claude/skills/assemble-ticket-context/SKILL.md:174-175`
- **Detail**: Step 6 confirms/asks for a destination path but never checks
  whether it already exists before writing, risking a silent clobber of a
  prior report. Not hypothetical — `<KEY>-context.md` is already sitting
  untracked in this repo root from an earlier run.
- **Fix**: Before writing, check if the destination file exists and ask the
  user to confirm overwrite (or pick a different name) if it does.
- **Decision**: FIXED — Step 6 now checks for an existing file at the
  destination path and asks the user to confirm overwrite or pick a
  different path before writing (`SKILL.md:174-178`).
