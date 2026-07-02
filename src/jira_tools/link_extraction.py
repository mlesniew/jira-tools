"""Extract Jira keys, issue links, and Confluence page references from ADF content.

Pure — no network calls. Walks an already-fetched `JiraTicket`'s or
`ConfluencePage`'s ADF content (plus, for tickets, the `issue_links` field
`atlassian_client.get_ticket()` already fetched) and returns typed,
deduplicated, sorted results.
"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from pydantic import BaseModel

from jira_tools.adf import ADFNode
from jira_tools.atlassian_client import ConfluencePage, JiraIssueLink, JiraTicket
from jira_tools.page_identifier import parse_page_id

_JIRA_KEY_PATTERN = re.compile(r"[A-Z][A-Z0-9]{1,9}-\d+")
_BROWSE_KEY_IN_URL = re.compile(r"/browse/([A-Z][A-Z0-9]{1,9}-\d+)")


def is_jira_key(identifier: str) -> bool:
    """Whether `identifier` is exactly a Jira-key-shaped token, e.g. `PROJ-1`."""
    return _JIRA_KEY_PATTERN.fullmatch(identifier) is not None


class TicketLinks(BaseModel):
    """Every Jira key, issue link, and Confluence page a ticket references."""

    jira_keys: list[str]
    issue_links: list[JiraIssueLink]
    confluence_page_ids: list[str]


class PageLinks(BaseModel):
    """Every Jira key and Confluence page a Confluence page references."""

    jira_keys: list[str]
    confluence_page_ids: list[str]


def extract_ticket_links(ticket: JiraTicket, site_url: str) -> TicketLinks:
    """Extract every Jira key, issue link, and Confluence page a ticket references."""
    jira_keys: set[str] = set()
    confluence_page_ids: set[str] = set()
    for root in (ticket.description, *(comment.body for comment in ticket.comments)):
        found_keys, found_pages = _walk(root, site_url)
        jira_keys |= found_keys
        confluence_page_ids |= found_pages
    return TicketLinks(
        jira_keys=sorted(jira_keys),
        issue_links=ticket.issue_links,
        confluence_page_ids=sorted(confluence_page_ids),
    )


def extract_page_links(page: ConfluencePage, site_url: str) -> PageLinks:
    """Extract every Jira key and Confluence page a Confluence page references."""
    jira_keys, confluence_page_ids = _walk(page.body, site_url)
    return PageLinks(jira_keys=sorted(jira_keys), confluence_page_ids=sorted(confluence_page_ids))


def _walk(node: ADFNode | None, site_url: str) -> tuple[set[str], set[str]]:
    jira_keys: set[str] = set()
    confluence_page_ids: set[str] = set()
    if node is None:
        return jira_keys, confluence_page_ids

    if node.text is not None:
        jira_keys.update(_JIRA_KEY_PATTERN.findall(node.text))

    for mark in node.marks:
        if mark.get("type") != "link":
            continue
        attrs = mark.get("attrs")
        href = attrs.get("href") if isinstance(attrs, dict) else None
        if isinstance(href, str):
            _categorize_url(href, site_url, jira_keys, confluence_page_ids)

    if node.type in ("inlineCard", "blockCard", "embedCard"):
        url = node.attrs.get("url")
        if isinstance(url, str):
            _categorize_url(url, site_url, jira_keys, confluence_page_ids)

    for child in node.content or []:
        child_keys, child_pages = _walk(child, site_url)
        jira_keys |= child_keys
        confluence_page_ids |= child_pages

    return jira_keys, confluence_page_ids


def _categorize_url(
    url: str, site_url: str, jira_keys: set[str], confluence_page_ids: set[str]
) -> None:
    if urlsplit(url).netloc.lower() != urlsplit(site_url).netloc.lower():
        return
    match = _BROWSE_KEY_IN_URL.search(url)
    if match:
        jira_keys.add(match.group(1))
        return
    try:
        confluence_page_ids.add(parse_page_id(url))
    except ValueError:
        pass
