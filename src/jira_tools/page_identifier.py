"""Parse a user-supplied Confluence page identifier into a bare page ID.

Pure parsing logic — no network calls, no client knowledge. Accepts either a
bare numeric page ID or a Confluence Cloud pretty-URL copied from the browser.
"""

from __future__ import annotations

import re

_PAGE_ID_IN_URL = re.compile(r"/pages/(\d+)(?:/|$)")


def parse_page_id(identifier: str) -> str:
    """Turn a bare page ID or a Confluence Cloud page URL into a bare page ID."""
    if identifier.isdigit():
        return identifier
    match = _PAGE_ID_IN_URL.search(identifier)
    if match:
        return match.group(1)
    raise ValueError(f"Unrecognized page identifier: {identifier!r}")
