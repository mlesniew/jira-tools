---
starter_id: python-cli
package_manager: uv
project_name: jira-tools
hints:
  language_family: python
  team_size: solo
  deployment_target: self-host
  ci_provider: github-actions
  ci_default_flow: manual-promotion
  bootstrapper_confidence: best-effort
  path_taken: custom
  quality_override: true
  self_check_answers:
    typed: false
    from_official_starter: false
    conventions: true
    docs_current: false
    can_judge_agent: true
  has_auth: false
  has_payments: false
  has_realtime: false
  has_ai: true
  has_background_jobs: false
---

## Why this stack

Solo, after-hours, one-week build of a read-only Jira/Confluence context
assembler — Atlassian REST/`acli` retrieval, ADF(JSON)→Markdown conversion, and
Claude-skill integration. The recorded preference is Python-first, and Python is
the strongest fit: mature libraries (`atlassian-python-api`/`httpx`,
`markdownify`, `click`/`typer`) collapse most of the retrieval and conversion
work, keeping the build weekend-sized. The curated starter registry has no
Python CLI starter (the `(cli, python)` cell is `<none>`), so this is an
**off-registry** choice — scaffold manually with `uv init` rather than
`/10x-bootstrapper`, which has no card for it; hence `best-effort` confidence and
a non-registry `starter_id`. `has_ai` is set (live context loading + research
helper); no app auth (single-user under the operator's own Atlassian
credentials), no payments, realtime, or background jobs. The `typed`
agent-friendly gate is the one real gap (Python is untyped by default); close it
by enforcing type hints + `mypy` (and `pydantic` at the ADF boundary) and
documenting CLI/layout conventions in `AGENTS.md`/`CLAUDE.md`. The author can
judge idiomatic Python, which carries the off-registry risk.
</content>
</invoke>
