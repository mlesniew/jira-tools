from typer.testing import CliRunner

from jira_tools.cli import app

runner = CliRunner()


def test_version_command_exits_zero() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 0
