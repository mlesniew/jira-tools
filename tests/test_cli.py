from pathlib import Path

import pytest
import responses
from typer.testing import CliRunner

from jira_tools.cli import app

runner = CliRunner()

JIRA_MYSELF_URL = "https://example.atlassian.net/rest/api/2/myself"
CONFLUENCE_CURRENT_USER_URL = "https://example.atlassian.net/wiki/rest/api/user/current"

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


@responses.activate
def test_auth_check_never_leaks_token(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_config(tmp_path, monkeypatch)
    responses.add(responses.GET, JIRA_MYSELF_URL, json={"message": "Unauthorized"}, status=401)
    responses.add(
        responses.GET, CONFLUENCE_CURRENT_USER_URL, json={"message": "Unauthorized"}, status=401
    )

    result = runner.invoke(app, ["auth-check"])

    assert "s3cr3t-token" not in result.stdout
    assert "s3cr3t-token" not in result.stderr


def test_auth_check_help_shows_description() -> None:
    result = runner.invoke(app, ["auth-check", "--help"])

    assert result.exit_code == 0
    assert "Confirm Jira and Confluence Cloud credentials work" in result.stdout
