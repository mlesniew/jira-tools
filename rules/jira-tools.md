# jira-tools

A read-only CLI that fetches Jira tickets and Confluence pages as clean
Markdown. Installed globally via `uv tool install .` — call it directly, no
`uv run` prefix needed:

- `jira-tools auth-check` — verify Jira/Confluence credentials work.
- `jira-tools fetch-ticket <KEY>` — fetch a Jira ticket as Markdown.
- `jira-tools fetch-page <ID>` — fetch a Confluence page as Markdown.
- `jira-tools extract-links <KEY>` — list Jira keys, issue links, and
  Confluence pages referenced by a ticket.
- `jira-tools version` — print the installed version.

The `assemble-ticket-context` skill uses these commands to assemble a Jira
ticket's full one-hop context (the ticket plus every directly-linked ticket
and referenced Confluence page) for meeting prep.
