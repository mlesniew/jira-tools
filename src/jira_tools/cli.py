from collections.abc import Callable

import typer

from jira_tools.atlassian_client import (
    IdentityCheckResult,
    ReadOnlyConfluenceClient,
    ReadOnlyJiraClient,
)
from jira_tools.config import ConfigError, config_path, load_config, permission_warning
from jira_tools.ticket_document import build_ticket_document

app = typer.Typer(
    name="jira-tools",
    help="Assemble Jira ticket and Confluence page context into readable Markdown.",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the installed jira-tools version."""
    from importlib.metadata import version as pkg_version

    typer.echo(pkg_version("jira-tools"))


@app.command(name="auth-check")
def auth_check() -> None:
    """Confirm Jira and Confluence Cloud credentials work, without printing the token."""
    path = config_path()
    try:
        if path.is_file() and (warning := permission_warning(path)):
            typer.echo(warning, err=True)
        config = load_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    jira_ok = _report("Jira", lambda: ReadOnlyJiraClient(config).whoami())
    confluence_ok = _report("Confluence", lambda: ReadOnlyConfluenceClient(config).whoami())

    if not (jira_ok and confluence_ok):
        raise typer.Exit(code=1)


@app.command(name="fetch-ticket")
def fetch_ticket(key: str) -> None:
    """Fetch a Jira ticket and print it as Markdown."""
    path = config_path()
    try:
        if path.is_file() and (warning := permission_warning(path)):
            typer.echo(warning, err=True)
        config = load_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    try:
        ticket = ReadOnlyJiraClient(config).get_ticket(key)
    except Exception:
        typer.echo(f"Could not fetch ticket {key}: not found or not accessible.", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(build_ticket_document(ticket))


def _report(product: str, whoami: Callable[[], IdentityCheckResult]) -> bool:
    try:
        result = whoami()
    except Exception as exc:
        typer.echo(f"{product}: FAIL ({exc})")
        return False
    typer.echo(f"{product}: PASS (as {result.display_name})")
    return True
