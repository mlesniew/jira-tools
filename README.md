# jira-tools

Read-only CLI that assembles a Jira ticket's one-hop context — the ticket
itself plus every directly-linked ticket and directly-referenced Confluence
page — into clean Markdown, for meeting prep and Claude analysis.

See `context/foundation/prd.md` for the full product requirements.

## Development

```
uv sync
uv run jira-tools --help
uv run pytest
uv run mypy
uv run ruff check .
```
