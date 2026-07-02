"""Assemble a Confluence page's fields into a single readable Markdown document.

Pure template/layout logic — no network calls, no I/O. Content conversion
itself is `adf.py`'s job.
"""

from __future__ import annotations

from jira_tools import adf
from jira_tools.atlassian_client import ConfluencePage

_NO_CONTENT = "*No content.*"
_FIDELITY_NOTE = (
    "*Some content (macros, panels, embeds) may have been simplified during conversion.*"
)


def build_page_document(page: ConfluencePage) -> str:
    """Render a `ConfluencePage` as a Markdown document."""
    lines = [
        f"# {page.title}",
        "",
        f"**Confluence page {page.id}** · {page.status}",
        "",
        adf.to_markdown(page.body) if page.body else _NO_CONTENT,
        "",
        _FIDELITY_NOTE,
        "",
    ]
    return "\n".join(lines)
