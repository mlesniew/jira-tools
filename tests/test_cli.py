import json
from pathlib import Path

import pytest
import responses
from typer.testing import CliRunner

from jira_tools.cli import app

runner = CliRunner()

JIRA_MYSELF_URL = "https://example.atlassian.net/rest/api/2/myself"
CONFLUENCE_CURRENT_USER_URL = "https://example.atlassian.net/wiki/rest/api/user/current"
JIRA_ISSUE_URL = "https://example.atlassian.net/rest/api/3/issue/PROJ-1"
JIRA_COMMENTS_URL = "https://example.atlassian.net/rest/api/3/issue/PROJ-1/comment"
CONFLUENCE_PAGE_URL = "https://example.atlassian.net/wiki/api/v2/pages/12345"

_ADF_TEXT_DOC = {
    "type": "doc",
    "content": [{"type": "paragraph", "content": [{"type": "text", "text": "hello"}]}],
}

VALID_TOML = """
site_url = "https://example.atlassian.net"
email = "user@example.com"
api_token = "s3cr3t-token"
"""


def _write_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_dir = tmp_path / "jira-tools"
    config_dir.mkdir()
    (config_dir / "config.toml").write_text(VALID_TOML)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


def test_version_command_exits_zero() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0


@responses.activate
def test_auth_check_passes_when_both_products_succeed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(responses.GET, JIRA_MYSELF_URL, json={"displayName": "Jane Doe"}, status=200)
    responses.add(
        responses.GET, CONFLUENCE_CURRENT_USER_URL, json={"displayName": "Jane Doe"}, status=200
    )

    result = runner.invoke(app, ["auth-check"])

    assert result.exit_code == 0
    assert "Jira: PASS (as Jane Doe)" in result.stdout
    assert "Confluence: PASS (as Jane Doe)" in result.stdout


@responses.activate
def test_auth_check_fails_when_jira_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(responses.GET, JIRA_MYSELF_URL, json={"message": "Unauthorized"}, status=401)
    responses.add(
        responses.GET, CONFLUENCE_CURRENT_USER_URL, json={"displayName": "Jane Doe"}, status=200
    )

    result = runner.invoke(app, ["auth-check"])

    assert result.exit_code != 0
    assert "Jira: FAIL" in result.stdout
    assert "Confluence: PASS (as Jane Doe)" in result.stdout


@responses.activate
def test_auth_check_fails_when_both_products_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(responses.GET, JIRA_MYSELF_URL, json={"message": "Unauthorized"}, status=401)
    responses.add(
        responses.GET, CONFLUENCE_CURRENT_USER_URL, json={"message": "Unauthorized"}, status=401
    )

    result = runner.invoke(app, ["auth-check"])

    assert result.exit_code != 0
    assert "Jira: FAIL" in result.stdout
    assert "Confluence: FAIL" in result.stdout


def test_auth_check_missing_config_names_expected_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    result = runner.invoke(app, ["auth-check"])

    assert result.exit_code != 0
    assert "jira-tools/config.toml" in result.stderr


@pytest.mark.parametrize(
    "jira_status,confluence_status",
    [(200, 200), (401, 200), (401, 401)],
    ids=["both-pass", "jira-fails", "both-fail"],
)
@responses.activate
def test_auth_check_never_leaks_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, jira_status: int, confluence_status: int
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(
        responses.GET,
        JIRA_MYSELF_URL,
        json={"displayName": "Jane Doe"} if jira_status == 200 else {"message": "Unauthorized"},
        status=jira_status,
    )
    responses.add(
        responses.GET,
        CONFLUENCE_CURRENT_USER_URL,
        json={"displayName": "Jane Doe"}
        if confluence_status == 200
        else {"message": "Unauthorized"},
        status=confluence_status,
    )

    result = runner.invoke(app, ["auth-check"])

    assert "s3cr3t-token" not in result.stdout
    assert "s3cr3t-token" not in result.stderr


def test_auth_check_never_leaks_token_on_missing_config(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    result = runner.invoke(app, ["auth-check"])

    assert "s3cr3t-token" not in result.stdout
    assert "s3cr3t-token" not in result.stderr


def test_auth_check_help_shows_description() -> None:
    result = runner.invoke(app, ["auth-check", "--help"])

    assert result.exit_code == 0
    assert "Confirm Jira and Confluence Cloud credentials work" in result.stdout


@responses.activate
def test_fetch_ticket_prints_markdown_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
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
            "comments": [
                {
                    "id": "10000",
                    "author": {"displayName": "Jane Doe"},
                    "created": "2026-01-01T00:00:00.000+0000",
                    "body": _ADF_TEXT_DOC,
                }
            ],
        },
        status=200,
    )

    result = runner.invoke(app, ["fetch-ticket", "PROJ-1"])

    assert result.exit_code == 0
    assert "# Something is broken" in result.stdout
    assert "PROJ-1" in result.stdout
    assert "### Comment by Jane Doe" in result.stdout


@responses.activate
def test_fetch_ticket_fails_cleanly_on_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(responses.GET, JIRA_ISSUE_URL, json={"message": "Not Found"}, status=404)

    result = runner.invoke(app, ["fetch-ticket", "PROJ-1"])

    assert result.exit_code != 0
    assert "PROJ-1" in result.stderr
    assert "Traceback" not in result.stderr


@responses.activate
def test_fetch_ticket_never_leaks_token_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
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
        json={"startAt": 0, "maxResults": 50, "total": 0, "comments": []},
        status=200,
    )

    result = runner.invoke(app, ["fetch-ticket", "PROJ-1"])

    assert "s3cr3t-token" not in result.stdout
    assert "s3cr3t-token" not in result.stderr


@responses.activate
def test_fetch_ticket_never_leaks_token_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(responses.GET, JIRA_ISSUE_URL, json={"message": "Not Found"}, status=404)

    result = runner.invoke(app, ["fetch-ticket", "PROJ-1"])

    assert "s3cr3t-token" not in result.stdout
    assert "s3cr3t-token" not in result.stderr


@responses.activate
def test_fetch_page_prints_markdown_document(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
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

    result = runner.invoke(app, ["fetch-page", "12345"])

    assert result.exit_code == 0
    assert "# A Page" in result.stdout
    assert "12345" in result.stdout
    assert "hello" in result.stdout


@responses.activate
def test_fetch_page_accepts_pretty_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_config(tmp_path, monkeypatch)
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

    result = runner.invoke(
        app,
        ["fetch-page", "https://example.atlassian.net/wiki/spaces/ENG/pages/12345/A+Page"],
    )

    assert result.exit_code == 0
    assert "# A Page" in result.stdout


@responses.activate
def test_fetch_page_fails_cleanly_on_not_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(responses.GET, CONFLUENCE_PAGE_URL, json={"message": "Not Found"}, status=404)

    result = runner.invoke(app, ["fetch-page", "12345"])

    assert result.exit_code != 0
    assert "12345" in result.stderr
    assert "Traceback" not in result.stderr


def test_fetch_page_fails_cleanly_on_bad_identifier_before_network_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)

    result = runner.invoke(app, ["fetch-page", "not-a-real-identifier"])

    assert result.exit_code != 0
    assert "not-a-real-identifier" in result.stderr
    assert "Traceback" not in result.stderr


@responses.activate
def test_fetch_page_never_leaks_token_on_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
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

    result = runner.invoke(app, ["fetch-page", "12345"])

    assert "s3cr3t-token" not in result.stdout
    assert "s3cr3t-token" not in result.stderr


@responses.activate
def test_fetch_page_never_leaks_token_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(responses.GET, CONFLUENCE_PAGE_URL, json={"message": "Not Found"}, status=404)

    result = runner.invoke(app, ["fetch-page", "12345"])

    assert "s3cr3t-token" not in result.stdout
    assert "s3cr3t-token" not in result.stderr
