import json

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
CONFLUENCE_PAGE_URL = "https://example.atlassian.net/wiki/api/v2/pages/12345"

_ADF_TEXT_DOC = {
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}],
}

# Confluence Cloud's v2 API error bodies are JSON:API-shaped and have no
# top-level "message" key (unlike the legacy v1 API) — the realistic shape
# for a get_page() 404, used to exercise the real error path rather than a
# body that happens to dodge it.
_CONFLUENCE_V2_ERROR_BODY = {
    "errors": [
        {"status": "404", "code": "not-found", "title": "No content found with the given id"}
    ]
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
        ReadOnlyConfluenceClient: ["whoami", "get_page"],
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


@responses.activate
def test_get_page_returns_title_status_and_body() -> None:
    responses.add(
        responses.GET,
        CONFLUENCE_PAGE_URL,
        json={
            "id": "12345",
            "title": "A Page",
            "status": "current",
            "body": {"atlas_doc_format": {"value": json.dumps(_ADF_TEXT_DOC)}},
        },
        status=200,
    )

    page = ReadOnlyConfluenceClient(_config()).get_page("12345")

    assert page.id == "12345"
    assert page.title == "A Page"
    assert page.status == "current"
    assert page.body is not None


@responses.activate
def test_get_page_with_missing_body_returns_none() -> None:
    responses.add(
        responses.GET,
        CONFLUENCE_PAGE_URL,
        json={"id": "12345", "title": "A Page", "status": "current", "body": {}},
        status=200,
    )

    page = ReadOnlyConfluenceClient(_config()).get_page("12345")

    assert page.body is None


@responses.activate
def test_get_page_raises_on_not_found() -> None:
    responses.add(responses.GET, CONFLUENCE_PAGE_URL, json=_CONFLUENCE_V2_ERROR_BODY, status=404)

    with pytest.raises(HTTPError):
        ReadOnlyConfluenceClient(_config()).get_page("12345")


@responses.activate
def test_get_page_not_found_does_not_leak_library_internals(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # atlassian-python-api's Confluence.raise_for_status assumes error bodies
    # always carry a top-level "message" key; real Confluence Cloud v2 error
    # bodies (like _CONFLUENCE_V2_ERROR_BODY) don't, which raises an internal
    # KeyError the library logs via log.error(exc) — and with no handler
    # configured, that reaches stderr via logging's last-resort handler
    # outside pytest. The module-level logger suppression in
    # atlassian_client.py must keep this from ever being emitted.
    responses.add(responses.GET, CONFLUENCE_PAGE_URL, json=_CONFLUENCE_V2_ERROR_BODY, status=404)

    with pytest.raises(HTTPError):
        ReadOnlyConfluenceClient(_config()).get_page("12345")

    assert not any(record.name.startswith("atlassian") for record in caplog.records)
