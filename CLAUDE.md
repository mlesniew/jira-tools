# jira-tools

CLI that assembles Jira ticket + linked Confluence page context into readable
Markdown. See `context/foundation/prd.md` for full requirements.

## Conventions

- Package manager: `uv`. Use `uv run <cmd>`, `uv add <pkg>`, `uv add --dev <pkg>`.
- Source lives under `src/jira_tools/`; tests under `tests/`.
- CLI commands are defined in `src/jira_tools/cli.py` using Typer, one
  `@app.command()` per subcommand (`fetch-ticket`, `fetch-page`, `assemble`, ...).
- Fully typed: `mypy --strict` must pass. Use `pydantic` models at the ADF
  (Atlassian JSON) boundary — never pass raw dicts across module boundaries.
- Lint/format with `ruff check .`.
- Guardrails (see PRD): strictly read-only against Jira/Confluence, no
  credentials in output/logs/cache, degrade gracefully on inaccessible links
  rather than crashing.

## Checks before considering a change done

```
uv run ruff check .
uv run mypy
uv run pytest
```
