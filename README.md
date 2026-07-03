# jira-tools

A growing library of reusable Claude Code **skills** for working with Jira
and Confluence, plus the small **rules** and **CLI** that support them.

The real value here isn't the CLI — it's the skills. Each one pairs the
CLI's deterministic, read-only access to Jira and Confluence with an LLM's
ability to synthesize and reason over what it fetches: the CLI guarantees
you always get clean, accurate, credential-safe data; the skill decides
what to do with it. That combination — reliable retrieval plus creative
analysis — is where this repo earns its keep, more so than any single tool
in it.

- **Skills** (`skills/`) — the invokable workflows themselves. Today there's
  one, `assemble-ticket-context` (pulls a Jira ticket's full one-hop context
  — the ticket plus every directly-linked ticket and referenced Confluence
  page — and summarizes it for meeting prep). It's meant to be the first of
  a growing library, not the whole of it.
- **Rules** (`rules/jira-tools.md`) — a short, always-on block of global
  instructions, injected into `~/.claude/CLAUDE.md`, that teaches every
  Claude Code session how to call the CLI correctly.
- **CLI** (`src/jira_tools/`) — the deterministic engine underneath: a
  read-only tool that fetches Jira tickets and Confluence pages as clean
  Markdown. It's what the skills and rules are built on top of, not the
  point of the repo on its own.

## Get started

Clone the repo, then paste this prompt into Claude Code:

```
Clone this repo if you haven't already:
git clone git@github.com:mlesniew/jira-tools.git

Follow the steps in `installation-steps.md` to set me up with jira-tools:
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

## Scope & distribution

This repo *is* the package — a single source of truth the team pulls with
`git clone` plus `install.py`, rather than a published npm/PyPI package. For
a small team already on GitHub, a clone is enough; a package registry
(versioned publishing, read tokens, private access control) would be more
machinery than this audience needs. A few boundaries are deliberate:

- **Versioning** is done with git tags, starting at `v1.0.0`. `git tag` is
  the release list, and each tag is a fixed point teammates can pin a clone
  to.
- **Claude Code only.** That's the tool the team uses. The skill format
  (`SKILL.md`) is portable, so a Cursor/Codex target would be a later
  tool-profile addition to `install.py`, not a rewrite.
- **No uninstall yet.** MVP scope. `install.py` is idempotent, so re-running
  it to update or repair an install is safe; a manifest-based uninstall can
  follow if the toolkit grows.

## Development

```
uv sync
uv run jira-tools --help
uv run pytest
uv run mypy
uv run ruff check .
```

See `context/foundation/prd.md` for the full product requirements.
