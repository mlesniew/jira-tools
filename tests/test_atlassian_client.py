import pytest
import responses
from pydantic import SecretStr
from requests.exceptions import HTTPError

from jira_tools.atlassian_client import ReadOnlyConfluenceClient, ReadOnlyJiraClient
from jira_tools.config import AtlassianConfig

JIRA_MYSELF_URL = "https://example.atlassian.net/rest/api/2/myself"
CONFLUENCE_CURRENT_USER_URL = "https://example.atlassian.net/wiki/rest/api/user/current"
JIRA_ISSUE_URL = "https://example.atlassian.net/rest/api/3/issue/PROJ-1"
JIRA_COMMENTS_URL = "https://example.atlassian.net/rest/api/3/issue/PROJ-1/comment"

_ADF_TEXT_DOC = {
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}],
}


def _comment(comment_id: str, author: str) -> dict[str, object]:
    return {
        "id": comment_id,
        "author": {"displayName": author},
        "created": "2026-01-01T00:00:00.000+0000",
        "body": _ADF_TEXT_DOC,
    }


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

    with pytest.raises(HTTPError):
        ReadOnlyJiraClient(_config()).whoami()


@responses.activate
def test_confluence_whoami_raises_on_unauthorized() -> None:
    responses.add(
        responses.GET, CONFLUENCE_CURRENT_USER_URL, json={"message": "Unauthorized"}, status=401
    )

    with pytest.raises(HTTPError):
        ReadOnlyConfluenceClient(_config()).whoami()


def test_wrapper_classes_expose_no_write_implying_method() -> None:
    write_keywords = ("create", "update", "delete", "remove", "add", "set", "put", "post")
    expected_public_methods = {
        ReadOnlyJiraClient: ["whoami", "get_ticket"],
        ReadOnlyConfluenceClient: ["whoami"],
    }
    for cls, expected in expected_public_methods.items():
        public_methods = [name for name in vars(cls) if not name.startswith("_")]
        assert public_methods == expected
        for name in public_methods:
            assert not any(keyword in name.lower() for keyword in write_keywords)


@responses.activate
def test_get_ticket_returns_summary_status_type_and_comments() -> None:
    responses.add(
        responses.GET,
        JIRA_ISSUE_URL,
        json={
            "key": "PROJ-1",
            "fields": {
                "summary": "Something is broken",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "description": _ADF_TEXT_DOC,
            },
        },
        status=200,
    )
    responses.add(
        responses.GET,
        JIRA_COMMENTS_URL,
        json={
            "startAt": 0,
            "maxResults": 50,
            "total": 1,
            "comments": [_comment("10000", "Jane Doe")],
        },
        status=200,
    )

    ticket = ReadOnlyJiraClient(_config()).get_ticket("PROJ-1")

    assert ticket.key == "PROJ-1"
    assert ticket.summary == "Something is broken"
    assert ticket.status == "In Progress"
    assert ticket.issue_type == "Bug"
    assert ticket.description is not None
    assert len(ticket.comments) == 1
    assert ticket.comments[0].author == "Jane Doe"
    assert ticket.comments[0].created == "2026-01-01T00:00:00.000+0000"


@responses.activate
def test_get_ticket_collects_comments_across_multiple_pages() -> None:
    responses.add(
        responses.GET,
        JIRA_ISSUE_URL,
        json={
            "key": "PROJ-1",
            "fields": {
                "summary": "Something is broken",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "description": None,
            },
        },
        status=200,
    )
    responses.add(
        responses.GET,
        JIRA_COMMENTS_URL,
        json={
            "startAt": 0,
            "maxResults": 50,
            "total": 3,
            "comments": [_comment("10000", "Jane Doe"), _comment("10001", "John Roe")],
        },
        status=200,
    )
    responses.add(
        responses.GET,
        JIRA_COMMENTS_URL,
        json={
            "startAt": 50,
            "maxResults": 50,
            "total": 3,
            "comments": [_comment("10002", "Ada Lovelace")],
        },
        status=200,
    )

    ticket = ReadOnlyJiraClient(_config()).get_ticket("PROJ-1")

    assert ticket.description is None
    assert [comment.author for comment in ticket.comments] == [
        "Jane Doe",
        "John Roe",
        "Ada Lovelace",
    ]


@responses.activate
def test_get_ticket_raises_on_incomplete_comment_page() -> None:
    responses.add(
        responses.GET,
        JIRA_ISSUE_URL,
        json={
            "key": "PROJ-1",
            "fields": {
                "summary": "Something is broken",
                "status": {"name": "In Progress"},
                "issuetype": {"name": "Bug"},
                "description": None,
            },
        },
        status=200,
    )
    responses.add(
        responses.GET,
        JIRA_COMMENTS_URL,
        json={"startAt": 0, "maxResults": 50, "total": 3, "comments": []},
        status=200,
    )

    with pytest.raises(ValueError, match="incomplete page"):
        ReadOnlyJiraClient(_config()).get_ticket("PROJ-1")


@responses.activate
def test_get_ticket_raises_on_not_found() -> None:
    responses.add(responses.GET, JIRA_ISSUE_URL, json={"message": "Not Found"}, status=404)

    with pytest.raises(HTTPError):
        ReadOnlyJiraClient(_config()).get_ticket("PROJ-1")
