"""Read-only wrappers around atlassian-python-api's Jira and Confluence clients.

This module's public surface is the enforcement mechanism for the read-only
guardrail: it exposes only identity/read methods, never the underlying
library's write methods. S-01/S-02 extend this surface with their own read
methods rather than reaching into the underlying library directly.
"""

from __future__ import annotations

import json
import logging

from atlassian import Confluence, Jira
from pydantic import BaseModel

from jira_tools.adf import ADFNode
from jira_tools.config import AtlassianConfig

# atlassian-python-api logs internal parsing failures via log.error(exc) (e.g.
# Confluence.raise_for_status KeyError'ing on error bodies that lack a
# top-level "message" key, which real Confluence Cloud v2 error responses
# do). With no handler configured, Python's logging falls back to printing
# str(exc) straight to stderr — leaking implementation noise (and, via its
# DEBUG curl logging, credentials) into our CLI's clean error output. Silence
# it; we handle and report our own errors.
logging.getLogger("atlassian").setLevel(logging.CRITICAL)

_CONFLUENCE_CURRENT_USER_PATH = "rest/api/user/current"
_COMMENT_PAGE_SIZE = 50


class IdentityCheckResult(BaseModel):
    """The identity confirmed by a product's "who am I" endpoint."""

    display_name: str


class JiraComment(BaseModel):
    """A single comment on a Jira ticket."""

    author: str
    created: str
    body: ADFNode


class JiraIssueLink(BaseModel):
    """A single Jira issue-link relationship to another ticket."""

    key: str
    relation: str


class JiraTicket(BaseModel):
    """The subset of a Jira issue's fields this project's retrieval needs."""

    key: str
    summary: str
    status: str
    issue_type: str
    description: ADFNode | None
    comments: list[JiraComment]
    issue_links: list[JiraIssueLink] = []


class ReadOnlyJiraClient:
    """A read-only view of a Jira Cloud site."""

    def __init__(self, config: AtlassianConfig) -> None:
        self._client = Jira(
            url=config.site_url,
            username=config.email,
            password=config.api_token.get_secret_value(),
            cloud=True,
            timeout=10,
        )

    def whoami(self) -> IdentityCheckResult:
        """Confirm the configured credentials via Jira's current-user endpoint."""
        response = self._client.myself()  # type: ignore[no-untyped-call]
        return IdentityCheckResult(display_name=response["displayName"])

    def get_ticket(self, key: str) -> JiraTicket:
        """Fetch a ticket's summary/status/type/description, issue links, and comments."""
        url = f"{self._issue_url(key)}?fields=summary,description,status,issuetype,issuelinks"
        issue = self._client.get(url)
        if not isinstance(issue, dict):
            raise ValueError("Issue endpoint returned an unexpected response")
        fields = issue["fields"]
        description = fields.get("description")
        issue_links = []
        for raw_link in fields.get("issuelinks", []):
            linked_issue = raw_link.get("outwardIssue") or raw_link.get("inwardIssue")
            if linked_issue is None:
                # A restricted linked issue the caller can't view is omitted
                # entirely rather than crashing the whole ticket fetch.
                continue
            relation = (
                raw_link["type"]["outward"]
                if "outwardIssue" in raw_link
                else raw_link["type"]["inward"]
            )
            issue_links.append(JiraIssueLink(key=linked_issue["key"], relation=relation))
        return JiraTicket(
            key=issue["key"],
            summary=fields["summary"],
            status=fields["status"]["name"],
            issue_type=fields["issuetype"]["name"],
            description=ADFNode.model_validate(description) if description else None,
            comments=self._get_all_comments(key),
            issue_links=sorted(issue_links, key=lambda link: (link.key, link.relation)),
        )

    def _issue_url(self, key: str) -> str:
        # API v3 (not the library default, v2) is required here: v2 returns
        # description/comment bodies as plain wiki-markup strings, not ADF.
        return f"{self._client.resource_url('issue', api_version='3')}/{key}"

    def _get_all_comments(self, key: str) -> list[JiraComment]:
        comments: list[JiraComment] = []
        start_at = 0
        total = 1
        url = f"{self._issue_url(key)}/comment"
        while len(comments) < total:
            page = self._client.get(
                url, params={"startAt": start_at, "maxResults": _COMMENT_PAGE_SIZE}
            )
            if not isinstance(page, dict):
                raise ValueError("Comment endpoint returned an unexpected response")
            total = page["total"]
            raw_comments = page["comments"]
            if not raw_comments and len(comments) < total:
                raise ValueError("Comment endpoint returned an incomplete page")
            for raw_comment in raw_comments:
                comments.append(
                    JiraComment(
                        author=raw_comment["author"]["displayName"],
                        created=raw_comment["created"],
                        body=ADFNode.model_validate(raw_comment["body"]),
                    )
                )
            start_at += _COMMENT_PAGE_SIZE
        return comments


class ConfluencePage(BaseModel):
    """The subset of a Confluence page's fields this project's retrieval needs."""

    id: str
    title: str
    status: str
    body: ADFNode | None


class ReadOnlyConfluenceClient:
    """A read-only view of a Confluence Cloud site."""

    def __init__(self, config: AtlassianConfig) -> None:
        self._client = Confluence(  # type: ignore[no-untyped-call]
            url=config.site_url,
            username=config.email,
            password=config.api_token.get_secret_value(),
            cloud=True,
            timeout=10,
        )

    def whoami(self) -> IdentityCheckResult:
        """Confirm the configured credentials via Confluence's current-user endpoint."""
        response = self._client.get(_CONFLUENCE_CURRENT_USER_PATH)
        if not isinstance(response, dict):
            raise ValueError("Confluence current-user endpoint returned an unexpected response")
        return IdentityCheckResult(display_name=response["displayName"])

    def get_page(self, page_id: str) -> ConfluencePage:
        """Fetch a page's title, status, and body by ID."""
        response = self._client.get(
            self._page_url(page_id), params={"body-format": "atlas_doc_format"}
        )
        if not isinstance(response, dict):
            raise ValueError("Page endpoint returned an unexpected response")
        # The v2 pages endpoint returns the ADF body as a JSON-encoded
        # string (BodyType.value), unlike Jira's v3 issue API, where
        # fields.description is already a nested ADF object.
        raw_body = response.get("body", {}).get("atlas_doc_format", {}).get("value")
        return ConfluencePage(
            id=response["id"],
            title=response["title"],
            status=response["status"],
            body=ADFNode.model_validate(json.loads(raw_body)) if raw_body else None,
        )

    def _page_url(self, page_id: str) -> str:
        # The v1 content API (the library's wrapped get_page_by_id) predates
        # ADF-format bodies. Only the v2 pages endpoint supports
        # body-format=atlas_doc_format, and resource_url() can't build this
        # path cleanly (Confluence's default api_version would inject a
        # spurious "latest" segment), so this is a direct path string,
        # mirroring how the underlying library itself builds its own v2 calls.
        return f"api/v2/pages/{page_id}"
