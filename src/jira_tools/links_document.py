"""Assemble link-extraction results into a single readable Markdown document.

Pure template/layout logic — no network calls, no I/O.
"""

from __future__ import annotations

from jira_tools.link_extraction import PageLinks, TicketLinks

_NO_JIRA_KEYS = "*No Jira keys found.*"
_NO_ISSUE_LINKS = "*No issue links found.*"
_NO_CONFLUENCE_PAGES = "*No Confluence pages found.*"


def build_links_document(source: str, result: TicketLinks | PageLinks) -> str:
    """Render a `TicketLinks` or `PageLinks` result as a Markdown document."""
    lines = [f"# Links found in {source}", "", "## Jira keys", ""]
    if result.jira_keys:
        lines.extend(f"- {key}" for key in result.jira_keys)
    else:
        lines.append(_NO_JIRA_KEYS)
    lines.append("")

    if isinstance(result, TicketLinks):
        lines.append("## Issue links")
        lines.append("")
        if result.issue_links:
            lines.extend(f"- {link.key} ({link.relation})" for link in result.issue_links)
        else:
            lines.append(_NO_ISSUE_LINKS)
        lines.append("")

    lines.append("## Confluence pages")
    lines.append("")
    if result.confluence_page_ids:
        lines.extend(f"- {page_id}" for page_id in result.confluence_page_ids)
    else:
        lines.append(_NO_CONFLUENCE_PAGES)
    lines.append("")

    return "\n".join(lines)
