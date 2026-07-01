"""Read-only wrappers around atlassian-python-api's Jira and Confluence clients.

This module's public surface is the enforcement mechanism for the read-only
guardrail: it exposes only identity/read methods, never the underlying
library's write methods. S-01/S-02 extend this surface with their own read
methods rather than reaching into the underlying library directly.
"""

from __future__ import annotations

from atlassian import Confluence, Jira
from pydantic import BaseModel

from jira_tools.config import AtlassianConfig

_CONFLUENCE_CURRENT_USER_PATH = "rest/api/user/current"


class IdentityCheckResult(BaseModel):
    """The identity confirmed by a product's "who am I" endpoint."""

    display_name: str


class ReadOnlyJiraClient:
    """A read-only view of a Jira Cloud site."""

    def __init__(self, config: AtlassianConfig) -> None:
        self._client = Jira(
            url=config.site_url,
            username=config.email,
            password=config.api_token.get_secret_value(),
            cloud=True,
        )

    def whoami(self) -> IdentityCheckResult:
        """Confirm the configured credentials via Jira's current-user endpoint."""
        response = self._client.myself()  # type: ignore[no-untyped-call]
        return IdentityCheckResult(display_name=response["displayName"])


class ReadOnlyConfluenceClient:
    """A read-only view of a Confluence Cloud site."""

    def __init__(self, config: AtlassianConfig) -> None:
        self._client = Confluence(  # type: ignore[no-untyped-call]
            url=config.site_url,
            username=config.email,
            password=config.api_token.get_secret_value(),
            cloud=True,
        )

    def whoami(self) -> IdentityCheckResult:
        """Confirm the configured credentials via Confluence's current-user endpoint."""
        response = self._client.get(_CONFLUENCE_CURRENT_USER_PATH)
        if not isinstance(response, dict):
            raise ValueError("Confluence current-user endpoint returned an unexpected response")
        return IdentityCheckResult(display_name=response["displayName"])
