"""Pure ADF (Atlassian Document Format) to Markdown conversion.

This module has no Jira/Confluence knowledge — it only knows how to turn a
validated ADF node tree into a readable Markdown string via `marklas`.
"""

from __future__ import annotations

import marklas
from pydantic import BaseModel


class ADFNode(BaseModel):
    """A loose, single-shape model for any node in an ADF document tree."""

    type: str
    content: list[ADFNode] | None = None
    text: str | None = None
    marks: list[dict[str, object]] = []
    attrs: dict[str, object] = {}


def to_markdown(node: ADFNode) -> str:
    """Convert a validated ADF node tree to a best-effort Markdown string."""
    return marklas.to_md(node.model_dump(mode="json", exclude_none=True), plain=True)
