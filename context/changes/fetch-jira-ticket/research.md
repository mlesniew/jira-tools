---
date: 2026-07-01T16:58:00+02:00
researcher: Claude (Sonnet 5)
git_commit: 05c1178bd237c5f24bcb069ec5802ab40398ba00
branch: master
repository: jira-tools
topic: "Best way to convert ADF data to Markdown (libraries vs. custom code, best-effort/simple)"
tags: [research, codebase, adf, markdown, conversion, atlassian]
status: complete
last_updated: 2026-07-01
last_updated_by: Claude (Sonnet 5)
last_updated_note: "Added a hands-on smoke test: ran both marklas and atlas-doc-parser against a representative ADF sample and confirmed both convert correctly, closing Open Question #1"
---

# Research: Best way to convert ADF data to Markdown

**Date**: 2026-07-01T16:58:00+02:00
**Researcher**: Claude (Sonnet 5)
**Git Commit**: 05c1178bd237c5f24bcb069ec5802ab40398ba00
**Branch**: master
**Repository**: jira-tools

## Research Question

What is the best way to convert ADF (Atlassian Document Format) data to
Markdown? Check available libraries and investigate custom-written code.
Focus on simplicity — a best-effort approach that doesn't convert absolutely
everything, but is easy, simple, lightweight, and gets typical content
converted correctly.

## Summary

> **Updated 2026-07-01 (see [Follow-up Research](#follow-up-research-2026-07-01t1720000200)):**
> a later-arriving library-survey pass found **`marklas`**, which closes the
> one gap below (`atlas-doc-parser`'s missing typing) while matching or
> beating it on every other axis. **`marklas` is now the primary
> recommendation; `atlas-doc-parser` is the secondary option; the custom
> converter remains the fallback.** The analysis below is kept as originally
> written for context — read the Follow-up section for the current call.

**Original recommendation: use the `atlas-doc-parser` PyPI library as the
primary path, with a small hand-written recursive converter as the
deliberate fallback.**

`atlas-doc-parser` ([PyPI](https://pypi.org/project/atlas-doc-parser/),
[GitHub](https://github.com/MacHu-GWU/atlas_doc_parser-project)) is a
purpose-built Python library that does exactly this job: `NodeDoc.from_dict(adf_json).to_markdown()`.
It is MIT-licensed, has a single lightweight runtime dependency
(`func_args`), supports Python 3.10–3.13, and its `nodes/` package has one
file per ADF node type across 46 node types — comprehensive coverage of
Jira/Confluence content including tables, panels, media, expand sections,
and smart-link cards. This is the simplest possible integration: two method
calls, no hand-rolled tree walker needed.

Its one real gap against this project's conventions: **no `py.typed`
marker**, so `mypy --strict` treats it as an untyped import. This is not a
new problem for this codebase — `atlassian_client.py:38` already carries a
`# type: ignore[no-untyped-call]` for the equally-untyped `atlassian`
package — so the same isolated-ignore pattern applies cleanly at the one
import site.

The one thing this research could **not** verify without a live payload:
what `atlas-doc-parser`'s Markdown output actually looks like on a real
Jira ticket/Confluence page. Since human-readable output is a named NFR
(not incidental), **verify output quality against a real fixture before
committing to the library** — that's the concrete go/no-go gate, not a
library-vs-custom toss-up.

If the library's output quality doesn't hold up, the fallback is a
**hand-written recursive converter, ~150–250 lines**, covering the ~15
high-frequency node types (paragraph, heading, lists, codeBlock,
blockquote, hardBreak, marks) and dropping/placeholder-rendering the rare
ones (table, panel, media, expand, macros) per the project's own
"best-effort, graceful degradation" NFR. This path gets you a single loose
pydantic model, zero new dependencies, and native `mypy --strict` compliance
with no ignores — at the cost of writing and maintaining the node handlers
yourself.

A secondary finding: `context/foundation/tech-stack.md` names `markdownify`
as a candidate conversion library, but `markdownify` converts **HTML to
Markdown**, not JSON. It cannot operate on ADF directly. This is worth a
tech-stack.md correction (see Architecture Insights) — not a fork to
re-litigate, since both the PRD (FR-003, NFR) and this research's own title
("convert ADF data to Markdown") already commit to ADF-JSON as the input.

## Detailed Findings

### Library survey: `atlas-doc-parser`

- **What it is**: A Python library that parses ADF JSON into typed Python
  objects and converts to Markdown via `NodeDoc.from_dict(adf_json)` →
  `.to_markdown()`. Tagline: "Turn your Confluence pages and Jira issues
  into AI-ready Markdown." ([PyPI](https://pypi.org/project/atlas-doc-parser/),
  [docs](https://atlas-doc-parser.readthedocs.io/en/stable/))
- **License**: MIT (confirmed from repo `LICENSE.txt`, copyright Sanhe Hu).
- **Python support**: `>=3.10,<4.0` — compatible with this project's
  `requires-python = ">=3.12"` (pyproject.toml:9).
- **Runtime dependencies**: exactly one — `func_args>=1.0.1,<2.0.0`
  (confirmed from `pyproject.toml` on the repo). This is as lightweight as
  a third-party dependency gets.
- **Typing**: **No `py.typed` marker** in the package
  (`atlas_doc_parser/` directory listing has no `py.typed` file) — under
  `mypy --strict` this means the import is implicitly `Any` unless ignored
  or stubbed.
- **Node/mark coverage**: the `atlas_doc_parser/nodes/` directory contains
  46 files, one per node type — block nodes (doc, paragraph, heading,
  rule, blockquote, panel, decision_list, task_list, bullet_list,
  ordered_list, code_block, table + table_row/header/cell, media_group,
  media_single), inline nodes (text, hard_break, emoji, mention, date,
  status), list items (list_item, task_item, decision_item), media
  (media, media_inline), cards/embeds (block_card, embed_card,
  inline_card), and UI elements (expand, nested_expand, caption, extension).
  This is materially broader than the "common cases" the PRD asks for —
  the library doesn't need to be best-effort, it already aims at fuller
  fidelity.
- **Adoption/maintenance signals**: 13 stars, 4 forks, 1 open issue, CI/docs
  infrastructure in place, ReadTheDocs hosted — small but appears actively
  maintained, not abandoned.
- **Not investigated further — a weak alternative**: `atlas_doc_to_markdown`
  ([GitHub](https://github.com/averypelle/atlas_doc_to_markdown)), which
  appears to derive from the project above, has 0 stars/forks and a single
  August 2025 release. Not worth building on when the upstream project is
  healthier.

### Custom converter feasibility

ADF is a strict Prosemirror-style tree: `content: list[Node]` for
block/structural nesting, and `marks: list[Mark]` only on `text` nodes for
inline formatting (bold/italic/code/strike/link/etc. — note `link` is a
**mark on text**, not its own node).

- **High-frequency node types** (the realistic "80% case" for Jira
  tickets/comments and Confluence pages): `paragraph`, `text` + marks
  (`strong`, `em`, `code`, `strike`, `link`), `heading`, `bulletList` /
  `orderedList` / `listItem`, `codeBlock`, `hardBreak`, `blockquote`,
  `mention`, `emoji`, `inlineCard` (auto-linked URLs), `rule`.
- **Rare/exotic — safe to drop or placeholder-render**: `table`/`panel`/
  `media*`/`expand`/`extension` (macros)/`blockCard`/`layoutSection`.
  Consistent with the PRD's explicit acceptance that "unsupported
  macros/panels/embeds may be dropped" (prd.md:170–174).
- **Design**: one dispatch function keyed by `node.type` (dict or `match`
  statement), each handler emitting Markdown around a recursive call over
  `content`; a `fallback_handler` for unknown types that recurses into
  `content` if present, else returns raw `text` if present, else drops
  silently. Marks apply as an ordered set of wrap functions on `text` nodes
  (code should suppress other marks — code spans can't nest bold/italic
  cleanly in most renderers).
- **Known tricky edge cases**: nested lists need an explicit indent-depth
  parameter threaded through recursion (not a redesign); `hardBreak`
  (single line break within one paragraph) must be distinguished from a new
  `paragraph` node (full blank-line break); overlapping marks on the same
  text run need a defined precedence; `inlineCard`/`blockCard` carry no
  visible text, only a URL in `attrs`; `mention`/`emoji` need their
  `attrs.text` fallback rather than raw IDs; empty/whitespace-only
  paragraphs are common in Jira's editor output and should render as blank
  lines, not errors.
- **Size estimate**: ~15–18 block/inline handlers + ~6–8 mark handlers +
  tree-walk plumbing ≈ **150–250 lines** of typed Python, covering an
  estimated 85–90% of real-world ticket/page content.

### Architecture fit in this repo

- **Module placement**: a flat `src/jira_tools/adf.py` fits the existing
  flat-module layout (`src/jira_tools/atlassian_client.py`,
  `src/jira_tools/config.py`, `src/jira_tools/cli.py`); split into a
  package only if it grows past a few hundred lines.
- **Pydantic boundary (CLAUDE.md: "pydantic models at the ADF boundary —
  never pass raw dicts across module boundaries")**: for the custom-code
  path, a **single loose recursive model** is the right level of typing —
  not a full discriminated union per node type. Something like:

  ```python
  class ADFNode(BaseModel):
      type: str
      content: list["ADFNode"] | None = None
      text: str | None = None
      marks: list[dict[str, object]] = []
      attrs: dict[str, object] = {}
  ```

  This satisfies "no raw dicts across boundaries" while staying as small as
  the "simple/lightweight" brief asks for. A discriminated union (one
  pydantic class per node type, ~15+ classes) is more idiomatic pydantic
  but adds exactly the ceremony this task's brief says to avoid — reserve
  it only if strict per-field validation of ADF becomes a real need later.
  Parse at the one JSON boundary with `TypeAdapter(ADFNode).validate_python(raw)`
  (or plain `ADFNode.model_validate(raw)`), and treat that call as the only
  legitimate point of contact with raw JSON.
- **If using `atlas-doc-parser` instead**: the library's own `NodeDoc`
  becomes the boundary type; the untyped import gets a single
  `# type: ignore[import-untyped]` (or an `mypy` per-module override in
  `pyproject.toml`), mirroring the existing pattern at
  `src/jira_tools/atlassian_client.py:38` (`# type: ignore[no-untyped-call]`
  for the equally-untyped `atlassian` package). No new precedent needed —
  this codebase already accepts one untyped third-party boundary.
- **mypy --strict**: `pyproject.toml:32` (`[tool.mypy] strict = true`).
  Both paths are compatible; the library path needs one ignore, the custom
  path needs none.
- **CLI integration**: follows the existing `@app.command()` pattern in
  `src/jira_tools/cli.py`; the conversion module itself should stay a pure
  transformation with no network calls or credentials, consistent with the
  read-only-surface docstring at the top of `atlassian_client.py:1-6`.
- **Testing**: follow the existing `pytest` + fixture-based style used for
  `atlassian_client`/`config` tests — feed sample ADF JSON fixtures
  (real or representative payloads) through the converter and assert on
  Markdown output; assert that unsupported node types degrade gracefully
  (dropped/placeholder) rather than raising, per the NFR at
  `context/foundation/prd.md:170-174`.

### Historical context (from prior changes)

- `context/foundation/tech-stack.md:30-33` names `markdownify` as part of
  the stack rationale ("mature libraries (`atlassian-python-api`/`httpx`,
  `markdownify`, `click`/`typer`) collapse most of the retrieval and
  conversion work"). **This is inconsistent with the ADF-JSON boundary**:
  `markdownify` converts HTML → Markdown, not JSON → Markdown, so it
  cannot operate on ADF directly. It was written at the stack-selection
  stage, likely without pinning down that ADF is JSON, not HTML. Both
  Jira Cloud (`expand=renderedFields`) and Confluence Cloud
  (`body.view`/`body.export_view`) *can* alternatively serve rendered HTML
  instead of ADF/`atlas_doc_format` — so `markdownify` would only become
  relevant if a future decision deliberately re-routes retrieval to fetch
  HTML instead of ADF. That is a bigger architectural change than this
  research's scope (PRD FR-003 and CLAUDE.md's "ADF boundary" language both
  already commit to ADF JSON as the source), so it is **not** recommended
  here — but `tech-stack.md`'s `markdownify` mention should be corrected or
  removed during implementation to avoid confusing a future reader.
- `context/foundation/prd.md:170-174` (best-effort NFR) and
  `context/foundation/roadmap.md:~100-113` (referenced by the historical
  research sub-agent) already frame conversion as common-cases-only, with
  macro/panel/embed fidelity explicitly deferred and gaps meant to be
  visible rather than silent — consistent with both candidate approaches
  above.
- No prior change or archive document specifies *how* (library vs. custom
  code) conversion should be implemented beyond the `tech-stack.md`
  `markdownify` mention addressed above.

## Code References

- `src/jira_tools/atlassian_client.py:1-6` — read-only wrapper docstring;
  new ADF conversion code should follow the same "pure surface, no writes"
  principle.
- `src/jira_tools/atlassian_client.py:38` — existing precedent for a single
  `# type: ignore[no-untyped-call]` against an untyped third-party
  Atlassian dependency; the same pattern applies to `atlas-doc-parser` if
  chosen.
- `src/jira_tools/cli.py:19-24` (pattern) — `@app.command()` convention for
  wiring a new CLI entry point.
- `pyproject.toml:9` — `requires-python = ">=3.12"`, compatible with
  `atlas-doc-parser`'s `>=3.10,<4.0` constraint.
- `pyproject.toml:32` — `[tool.mypy] strict = true`.
- `context/foundation/prd.md:118-122` — FR-003, the must-have ADF→Markdown
  requirement (basic formatting only).
- `context/foundation/prd.md:170-174` — the best-effort conversion NFR.
- `context/foundation/tech-stack.md:30-33` — the `markdownify` mention to
  reconcile/correct.

## Architecture Insights

- The project's own guardrails (best-effort, graceful degradation, no raw
  dicts across boundaries) are satisfied by both candidate approaches; the
  deciding factor is **how much of the "readable Markdown" NFR you want to
  own versus delegate**. A library gives you breadth (46 node types) for
  near-zero code, at the cost of one untyped import and inheriting its
  formatting choices verbatim. Custom code gives you full control over
  exactly how each node renders (useful since human-readability is a named
  product requirement, not incidental) and zero new dependencies, at the
  cost of writing and maintaining ~150–250 lines yourself.
- Given this project explicitly asked for "simple, lightweight, easy" and
  already tolerates one untyped Atlassian dependency, `atlas-doc-parser` is
  the pragmatic default — but treat verifying its actual Markdown output on
  a real ticket/page fixture as the implementation-time gate before locking
  it in, since output readability is the one thing this research couldn't
  confirm without live data.
- The single loose `ADFNode` pydantic model (vs. a full discriminated
  union) is the right shape for the custom fallback — it matches "no raw
  dicts across boundaries" without importing the ceremony of one class per
  node type.

## Related Research

None yet — this is the first research document for this change.
(`context/changes/atlassian-readonly-auth/plan.md` covers the read-only
auth layer this conversion module will sit alongside, but does not address
ADF conversion.)

## Open Questions

1. **Output-quality verification** — `atlas-doc-parser`'s Markdown output
   has not been visually inspected against a real Jira ticket or
   Confluence page in this research; its docs quickstart shows only the
   two-call API (`NodeDoc.from_dict(adf_json).to_markdown()`), not a
   worked before/after example. Recommended as the concrete
   implementation-time check: run a real (or representative) ADF payload
   through it and compare against the custom-converter sketch's expected
   output before committing to either path.
2. **`tech-stack.md` correction** — decide whether to edit
   `context/foundation/tech-stack.md:30-33` to drop/replace the
   `markdownify` mention, since it doesn't apply to an ADF-JSON boundary.
   Owner: user.
3. **HTML-as-alternative-source** — noted only as an aside: Jira Cloud
   (`expand=renderedFields`) and Confluence Cloud (`body.view`/
   `body.export_view`) can serve rendered HTML instead of ADF, which would
   make `markdownify` directly applicable. Not recommended for this
   change since PRD/CLAUDE.md already commit to the ADF-JSON boundary, but
   flagged in case retrieval strategy is revisited later.

## Follow-up Research 2026-07-01T17:20:00+02:00

A library-survey sub-agent spawned earlier in this research (before the
original recommendation above was written) returned after the document was
already synthesized. It surfaced a stronger candidate than any considered
in the original pass. I independently verified the claims below directly
against the package's PyPI page, GitHub repo, and `pyproject.toml` before
accepting them.

### New candidate: `marklas` — closes the one gap `atlas-doc-parser` had

- **What it is**: a bidirectional Markdown ⟷ ADF converter —
  ([PyPI](https://pypi.org/project/marklas/),
  [GitHub](https://github.com/byExist/marklas)) — `to_adf()` / `to_md()`,
  plus a `Transformer` class for custom AST processing.
- **License**: MIT (confirmed).
- **Python support**: `>=3.11` (confirmed from `pyproject.toml`) —
  compatible with this project's `>=3.12`.
- **Runtime dependencies**: exactly one — `mistune>=3.2` (confirmed), a
  well-known, widely-used pure-Python Markdown parser. Comparable
  dependency weight to `atlas-doc-parser`.
- **Typing — the deciding difference**: ships a `py.typed` marker at
  `src/marklas/py.typed` (confirmed by directory listing) and declares
  `Typing :: Typed` as a PyPI classifier (confirmed from `pyproject.toml`).
  This means it satisfies `mypy --strict` **natively — no
  `# type: ignore` needed**, unlike `atlas-doc-parser`.
- **Maintenance signal**: latest release v0.8.2, pushed 2026-06-30 (the day
  before this research), 23 releases total, 17 GitHub stars. More
  active/recent than `atlas-doc-parser` (last push 2026-01-04) despite a
  smaller star count. The project itself is built with `uv`, matching this
  repo's own tooling.
- **Node coverage**: headings, lists, panels, tables, code blocks, media,
  mentions, expand sections, and extensions per its README — comparable
  breadth to `atlas-doc-parser`.
- **Best-effort mode is a first-class, documented feature** — not
  something to bolt on: `to_md(adf_document, plain=True)` strips
  ADF-specific round-trip metadata (which the library otherwise preserves
  as inline HTML with `adf` attributes for lossless round-tripping) and
  produces clean plain Markdown. This maps directly onto this project's
  "best-effort, readable-for-humans-and-LLMs" NFR — it's the exact mode
  this project wants, already built in, rather than something a custom
  converter or `atlas-doc-parser` would need to approximate.
- **Bonus signal for this project's use case**: the README claims a
  2.5–3.9x token reduction vs. raw ADF JSON — directly relevant to PRD
  FR-007 (live-loading assembled context into a Claude conversation),
  where context-window budget matters.

### Other candidates the survey ruled out (confirms the original survey's scope was reasonable, doesn't change the verdict)

- **`pyadf`** ([PyPI](https://pypi.org/project/pyadf/)) — MIT, actively
  pushed (2026-06-11), broad node coverage including task lists and
  colspan tables, ships a `.pyi` stub for its compiled core — but it's a
  **Rust/PyO3 native extension** (prebuilt wheels only, no pure-Python
  fallback) and self-declares **Alpha** status. The compiled-wheel
  dependency is exactly the kind of operational risk this project's
  "simple/lightweight" brief is trying to avoid; not recommended over a
  pure-Python option.
- **`pyadf2md`** ([GitHub](https://github.com/DiPaolo/pyadf2md)) — last
  push 2023-09-29, no PyPI release ever — abandoned, ruled out.
- **`atlassian-python-api`** (already a dependency of this project,
  confirmed via local `.venv`) — grepped directly; it has **no** ADF or
  Markdown conversion helpers. Confirms the earlier architecture-fit
  finding that conversion must come from a dedicated package or custom
  code, not the existing Atlassian client dependency.
- JS-only tools (`adf-to-md`, `md-to-adf`) confirmed not Python — same
  conclusion as the original research, not directly usable.

### Updated recommendation

**Use `marklas` as the primary path.** It has everything `atlas-doc-parser`
has (MIT, single lightweight dep, broad node coverage, active maintenance)
plus native `mypy --strict` compliance (no `type: ignore` needed anywhere)
and a purpose-built `plain=True` best-effort mode that matches this
project's stated NFR almost exactly. Integration shape is the same as
originally described for `atlas-doc-parser`: wrap it behind a thin adapter
in `src/jira_tools/adf.py` with pydantic models at the boundary per
CLAUDE.md, rather than depending on its internal AST shape directly (per
its own `ARCHITECTURE.md`/`Transformer` design, this is the intended
integration pattern, not a workaround).

`atlas-doc-parser` remains a reasonable secondary option — its node
coverage is at least as broad, and a single isolated `type: ignore`
consistent with the existing `atlassian_client.py:38` precedent is not a
blocker if `marklas` turns out to have some gap not caught here. The
hand-written custom converter (~150–250 lines) remains the fallback if
neither library's actual Markdown output holds up against a real payload.

**The one open question is unchanged and now applies to `marklas` first**:
its actual Markdown output on a real Jira ticket/Confluence page has not
been visually inspected in this research (no worked ADF→Markdown example
was found in its docs either). Verify `to_md(payload, plain=True)` output
against a real fixture before committing — same gate as before, just
pointed at the new primary candidate.

## Follow-up Research 2026-07-01T18:10:00+02:00 — hands-on smoke test

The user pushed back on relying on star counts (17 for `marklas`, 13 for
`atlas-doc-parser` — both weak signals) and asked to actually run a check.
**This closes Open Question #1.** Both libraries were `uv pip install`ed
into a scratch venv and run against the same representative ADF document
covering the high-frequency cases: `heading`, `paragraph` with `strong`/
`em`/`link` marks, a `mention`, a `bulletList` with an inline `code` mark,
a `codeBlock`, and a `panel` (the one "exotic" node included deliberately,
to see how each library degrades it).

**Sample input** (abbreviated — full JSON in scratch dir, not committed):
a heading, a paragraph with bold/italic/link/mention text, a two-item
bullet list (one item with inline code), a Python code block, and a
warning panel.

**`marklas` — `to_md(doc, plain=True)`:**

```markdown
## Ticket summary

This is **bold** and *italic* text with a [link](<https://example.com>) and a mention @Jane Doe.

- First item
- Second item with `inline code`

```python
def hello():
    print("hi")

```

<aside>

This is a warning panel.

</aside>
```

**`atlas-doc-parser` — `NodeDoc.from_dict(doc).to_markdown()`:**

```markdown
## Ticket summary

This is **bold** and *italic* text with a [link](https://example.com) and a mention @Jane Doe.

- First item
- Second item with `` inline code ``

```python
def hello():
    print("hi")

```

> **WARNING**
>
> This is a warning panel.
```

### Findings

- **Both convert the common-case content correctly and cleanly**: headings,
  bold/italic, links, mentions (with display-text fallback), bullet lists,
  inline code, and fenced code blocks all round-trip to readable Markdown
  with no errors, no exceptions, no dropped content. This is a real,
  positive result — not just a claim from a README.
- **`marklas`** wraps the link URL in angle brackets
  (`[link](<https://example.com>)`) — valid CommonMark, slightly unusual
  stylistically but renders correctly everywhere. `plain=True` fully
  stripped the ADF round-trip metadata as documented, leaving a bare
  `<aside>...</aside>` HTML block for the panel.
- **`atlas-doc-parser`** renders the panel as a Markdown blockquote with a
  bold type label (`> **WARNING**`) rather than raw HTML — arguably more
  "Markdown-native" and readable as plain text (e.g. in a terminal or a
  markdown renderer without HTML passthrough) than `marklas`'s `<aside>`
  tag. It also uses a double-backtick delimiter for inline code
  (`` `` inline code `` ``) where a single backtick would do — cosmetic,
  not incorrect. It also emitted one leading blank line before the first
  heading (minor cosmetic quirk).
- **Net**: no correctness gap between the two on this sample. The one
  stylistic edge goes to `atlas-doc-parser` for panel rendering
  (blockquote > raw HTML for a plain-Markdown-reading audience), while
  `marklas` still wins on the typing axis (native `mypy --strict`
  compliance, no `type: ignore` needed).

### Updated verdict

**`marklas` remains the recommended primary choice** — the typing win is
still the deciding factor, and this test found no functional reason to
prefer `atlas-doc-parser` instead. But this test also demonstrates
`atlas-doc-parser` is a genuinely safe secondary/fallback, not just a
theoretical one — both libraries are real, working, low-star-but-functional
options, and the low star counts on both do not indicate that either is
broken or unmaintained-in-practice. If `marklas`'s panel-as-raw-HTML output
turns out to be undesirable during implementation, either post-process that
one node type, or fall back to `atlas-doc-parser`'s blockquote rendering —
this is now a known, bounded difference rather than an unknown.
</content>
