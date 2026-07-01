import responses
from pydantic import SecretStr

from jira_tools.atlassian_client import ReadOnlyConfluenceClient, ReadOnlyJiraClient
from jira_tools.config import AtlassianConfig

JIRA_MYSELF_URL = "https://example.atlassian.net/rest/api/2/myself"
CONFLUENCE_CURRENT_USER_URL = "https://example.atlassian.net/wiki/rest/api/user/current"


def _config() -> AtlassianConfig:
    return AtlassianConfig(
        site_url="https://example.atlassian.net",
        email="user@example.com",
        api_token=SecretStr("s3cr3t-token"),
    )


@responses.activate
def test_jira_whoami_returns_display_name() -> None:
    responses.add(
        responses.GET,
        JIRA_MYSELF_URL,
        json={"accountId": "abc123", "displayName": "Jane Doe"},
        status=200,
    )

    result = ReadOnlyJiraClient(_config()).whoami()

    assert result.display_name == "Jane Doe"


@responses.activate
def test_confluence_whoami_returns_display_name() -> None:
    responses.add(
        responses.GET,
        CONFLUENCE_CURRENT_USER_URL,
        json={"accountId": "abc123", "displayName": "Jane Doe"},
        status=200,
    )

    result = ReadOnlyConfluenceClient(_config()).whoami()

    assert result.display_name == "Jane Doe"


@responses.activate
def test_jira_whoami_raises_on_unauthorized() -> None:
    responses.add(responses.GET, JIRA_MYSELF_URL, json={"message": "Unauthorized"}, status=401)

    try:
        ReadOnlyJiraClient(_config()).whoami()
    except Exception:
        pass
    else:
        raise AssertionError("expected whoami() to raise on a 401 response")


@responses.activate
def test_confluence_whoami_raises_on_unauthorized() -> None:
    responses.add(
        responses.GET, CONFLUENCE_CURRENT_USER_URL, json={"message": "Unauthorized"}, status=401
    )

    try:
        ReadOnlyConfluenceClient(_config()).whoami()
    except Exception:
        pass
    else:
        raise AssertionError("expected whoami() to raise on a 401 response")


def test_wrapper_classes_expose_no_write_implying_method() -> None:
    write_keywords = ("create", "update", "delete", "remove", "add", "set", "put", "post")
    for cls in (ReadOnlyJiraClient, ReadOnlyConfluenceClient):
        public_methods = [name for name in vars(cls) if not name.startswith("_")]
        assert public_methods == ["whoami"]
        for name in public_methods:
            assert not any(keyword in name.lower() for keyword in write_keywords)
