"""Pure ADF (Atlassian Document Format) to Markdown conversion.

This module has no Jira/Confluence knowledge — it only knows how to turn a
validated ADF node tree into a readable Markdown string via `marklas`.
"""

from __future__ import annotations

import re

import marklas
from pydantic import BaseModel

_CODE_SEGMENT = re.compile(r"(```.*?```|`[^`\n]*`)", re.DOTALL)


class ADFNode(BaseModel):
    """A loose, single-shape model for any node in an ADF document tree."""

    type: str
    content: list[ADFNode] | None = None
    text: str | None = None
    marks: list[dict[str, object]] = []
    attrs: dict[str, object] = {}


def to_markdown(node: ADFNode) -> str:
    """Convert a validated ADF node tree to a best-effort Markdown string."""
    markdown = marklas.to_md(node.model_dump(mode="json", exclude_none=True), plain=True)
    # marklas always renders ADF hardBreak nodes as literal `<br>` (a
    # deliberate choice for markdown round-trip fidelity, not affected by
    # plain=True) rather than a CommonMark hard line break. Convert it so
    # plain-text output reads as a normal line break instead of raw HTML,
    # but skip fenced code blocks and inline code spans so a literal `<br>`
    # pasted inside code isn't corrupted.
    segments = _CODE_SEGMENT.split(markdown)
    return "".join(
        segment if i % 2 == 1 else segment.replace("<br>", "  \n")
        for i, segment in enumerate(segments)
    )
