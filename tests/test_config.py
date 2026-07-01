from pathlib import Path

import pytest

from jira_tools.config import ConfigInvalidError, ConfigNotFoundError, load_config

VALID_TOML = """
site_url = "https://example.atlassian.net"
email = "user@example.com"
api_token = "s3cr3t-token"
"""


def _write_config(path: Path, content: str, mode: int = 0o600) -> Path:
    config_file = path / "config.toml"
    config_file.write_text(content)
    config_file.chmod(mode)
    return config_file


def test_load_config_valid_file(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path, VALID_TOML)

    config = load_config(config_file)

    assert config.site_url == "https://example.atlassian.net"
    assert config.email == "user@example.com"
    assert config.api_token.get_secret_value() == "s3cr3t-token"


def test_load_config_missing_file_names_expected_path(tmp_path: Path) -> None:
    missing_path = tmp_path / "config.toml"

    with pytest.raises(ConfigNotFoundError) as exc_info:
        load_config(missing_path)

    assert str(missing_path) in str(exc_info.value)
    assert "site_url" in str(exc_info.value)
    assert "email" in str(exc_info.value)
    assert "api_token" in str(exc_info.value)


def test_load_config_malformed_toml(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path, "not = valid = toml")

    with pytest.raises(ConfigInvalidError):
        load_config(config_file)


def test_load_config_missing_field_names_it(tmp_path: Path) -> None:
    config_file = _write_config(
        tmp_path,
        'site_url = "https://example.atlassian.net"\nemail = "user@example.com"\n',
    )

    with pytest.raises(ConfigInvalidError) as exc_info:
        load_config(config_file)

    assert "api_token" in str(exc_info.value)


def test_load_config_warns_on_world_readable(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = _write_config(tmp_path, VALID_TOML, mode=0o644)

    load_config(config_file)

    captured = capsys.readouterr()
    assert "Warning" in captured.err
    assert str(config_file) in captured.err


def test_load_config_no_warning_on_owner_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_file = _write_config(tmp_path, VALID_TOML, mode=0o600)

    load_config(config_file)

    captured = capsys.readouterr()
    assert captured.err == ""


def test_load_config_does_not_leak_token_in_repr(tmp_path: Path) -> None:
    config_file = _write_config(tmp_path, VALID_TOML)

    config = load_config(config_file)

    assert "s3cr3t-token" not in repr(config)
    assert "s3cr3t-token" not in str(config)
