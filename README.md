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

### Configuration

`jira-tools` reads Jira Cloud + Confluence Cloud credentials from
`$XDG_CONFIG_HOME/jira-tools/config.toml` (falling back to
`~/.config/jira-tools/config.toml` if `XDG_CONFIG_HOME` is unset). Create the
file with three fields:

```toml
site_url = "https://your-domain.atlassian.net"
email = "you@example.com"
api_token = "your-atlassian-api-token"
```

Generate an API token at
https://id.atlassian.com/manage-profile/security/api-tokens. The file should
be readable only by you (`chmod 600 ~/.config/jira-tools/config.toml`);
`jira-tools` warns on stderr if it's more open than that.

Verify the credentials work:

```
uv run jira-tools auth-check
```

This prints a PASS/FAIL line per product and exits non-zero if either check
fails. The token is never printed or logged.
