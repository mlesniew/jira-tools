"""Assemble a Jira ticket's fields into a single readable Markdown document.

Pure template/layout logic — no network calls, no I/O. Content conversion
itself is `adf.py`'s job.
"""

from __future__ import annotations

from jira_tools import adf
from jira_tools.atlassian_client import JiraTicket

_NO_DESCRIPTION = "*No description.*"
_NO_COMMENTS = "*No comments.*"


def build_ticket_document(ticket: JiraTicket) -> str:
    """Render a `JiraTicket` as a Markdown document."""
    lines = [
        f"# {ticket.summary}",
        "",
        f"**{ticket.key}** · {ticket.status} · {ticket.issue_type}",
        "",
        "## Description",
        "",
        adf.to_markdown(ticket.description) if ticket.description else _NO_DESCRIPTION,
        "",
        "## Comments",
        "",
    ]
    if ticket.comments:
        for comment in ticket.comments:
            lines.append(f"### Comment by {comment.author} ({comment.created})")
            lines.append("")
            lines.append(adf.to_markdown(comment.body))
            lines.append("")
    else:
        lines.append(_NO_COMMENTS)
        lines.append("")
    return "\n".join(lines)
