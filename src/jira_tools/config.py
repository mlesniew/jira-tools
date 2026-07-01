"""Typed config model and loader for Atlassian Cloud credentials."""

from __future__ import annotations

import os
import stat
import tomllib
from pathlib import Path

from pydantic import BaseModel, SecretStr, ValidationError

REQUIRED_FIELDS = ("site_url", "email", "api_token")


class AtlassianConfig(BaseModel):
    """Jira/Confluence Cloud credentials shared by both products."""

    site_url: str
    email: str
    api_token: SecretStr


class ConfigError(Exception):
    """Base class for config loading errors; messages are safe to print as-is."""


class ConfigNotFoundError(ConfigError):
    def __init__(self, path: Path) -> None:
        super().__init__(
            f"Config file not found at {path}. Create it with the fields: "
            f"{', '.join(REQUIRED_FIELDS)}."
        )


class ConfigInvalidError(ConfigError):
    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"Config file at {path} is invalid: {reason}")


def config_path() -> Path:
    """Resolve the XDG-aware config path, without checking it exists."""
    xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg_config_home) if xdg_config_home else Path.home() / ".config"
    return base / "jira-tools" / "config.toml"


def load_config(path: Path | None = None) -> AtlassianConfig:
    """Load and validate the Atlassian config file.

    Raises ConfigNotFoundError / ConfigInvalidError with actionable messages
    that never echo the file's raw contents or any credential value.
    """
    resolved_path = path if path is not None else config_path()

    if not resolved_path.is_file():
        raise ConfigNotFoundError(resolved_path)

    try:
        raw = tomllib.loads(resolved_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        raise ConfigInvalidError(resolved_path, "not valid TOML") from exc

    try:
        return AtlassianConfig.model_validate(raw)
    except ValidationError as exc:
        fields = ", ".join(sorted({str(error["loc"][0]) for error in exc.errors()}))
        raise ConfigInvalidError(
            resolved_path, f"missing or invalid field(s): {fields}"
        ) from None


def permission_warning(path: Path) -> str | None:
    """Return a warning message if the config file is group/other readable, else None."""
    mode = path.stat().st_mode
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        return f"Warning: {path} is readable by group/other; run `chmod 600 {path}`."
    return None
