# jira-tools

Read-only CLI that assembles a Jira ticket's one-hop context — the ticket
itself plus every directly-linked ticket and directly-referenced Confluence
page — into clean Markdown, for meeting prep and Claude analysis. Includes
the `assemble-ticket-context` Claude Code skill, which drives the CLI to
build that context and summarize it for you.

## Get started

Clone the repo, then paste this prompt into Claude Code:

```
Clone this repo if you haven't already:
git clone git@github.com:mlesniew/jira-tools.git

Follow the steps in `installation-steps` to set me up with jira-tools:
install uv if needed, run `uv tool install .`, help me create
~/.config/jira-tools/config.toml, and verify with `jira-tools auth-check`.
Then run `uv run python install.py` to install the skills and global
instructions.
```

The agent installs uv (if missing), runs `uv tool install .`, walks you
through the config file, verifies credentials with `auth-check`, then runs
`uv run python install.py` — which copies the skills into
`~/.claude/skills/` and adds a short `jira-tools` usage block to your global
`~/.claude/CLAUDE.md`. From then on, in any project, the
`assemble-ticket-context` skill is available and Claude knows how to call
`jira-tools`.

## Manual install

1. Make sure [uv](https://docs.astral.sh/uv/) is installed.
2. `git clone git@github.com:mlesniew/jira-tools.git && cd jira-tools`
3. `uv tool install .` — installs the `jira-tools` command. Verify with
   `jira-tools version`.
4. Create `~/.config/jira-tools/config.toml` (XDG-aware: honors
   `$XDG_CONFIG_HOME/jira-tools/config.toml` if set) with:

   ```toml
   site_url = "https://your-domain.atlassian.net"
   email = "you@example.com"
   api_token = "your-atlassian-api-token"
   ```

   Generate an API token at
   https://id.atlassian.com/manage-profile/security/api-tokens. The file
   should be readable only by you (`chmod 600
   ~/.config/jira-tools/config.toml`); `jira-tools` warns on stderr if it's
   more open than that.
5. Verify credentials: `jira-tools auth-check` — prints a PASS/FAIL line per
   product and exits non-zero if either check fails. The token is never
   printed or logged.
6. Run `uv run python install.py` from the clone to install the skills to
   `~/.claude/skills/` and inject the usage block into `~/.claude/CLAUDE.md`.
   Safe to re-run; it's idempotent and preserves any notes you've added
   outside the `jira-tools` markers.

## Development

```
uv sync
uv run jira-tools --help
uv run pytest
uv run mypy
uv run ruff check .
```

See `context/foundation/prd.md` for the full product requirements.
