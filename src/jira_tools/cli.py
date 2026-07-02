from collections.abc import Callable

import typer

from jira_tools.atlassian_client import (
    IdentityCheckResult,
    ReadOnlyConfluenceClient,
    ReadOnlyJiraClient,
)
from jira_tools.config import ConfigError, config_path, load_config, permission_warning
from jira_tools.link_extraction import (
    PageLinks,
    TicketLinks,
    extract_page_links,
    extract_ticket_links,
    is_jira_key,
)
from jira_tools.links_document import build_links_document
from jira_tools.page_document import build_page_document
from jira_tools.page_identifier import parse_page_id
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


@app.command(name="fetch-page")
def fetch_page(identifier: str) -> None:
    """Fetch a Confluence page and print it as Markdown."""
    try:
        page_id = parse_page_id(identifier)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    path = config_path()
    try:
        if path.is_file() and (warning := permission_warning(path)):
            typer.echo(warning, err=True)
        config = load_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    try:
        page = ReadOnlyConfluenceClient(config).get_page(page_id)
    except Exception:
        typer.echo(f"Could not fetch page {identifier}: not found or not accessible.", err=True)
        raise typer.Exit(code=1) from None

    typer.echo(build_page_document(page))


@app.command(name="extract-links")
def extract_links(identifier: str) -> None:
    """Extract Jira keys, issue links, and Confluence pages referenced by a ticket or page."""
    page_id: str | None = None
    if not is_jira_key(identifier):
        try:
            page_id = parse_page_id(identifier)
        except ValueError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(code=1) from exc

    path = config_path()
    try:
        if path.is_file() and (warning := permission_warning(path)):
            typer.echo(warning, err=True)
        config = load_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc

    result: TicketLinks | PageLinks
    if page_id is None:
        try:
            ticket = ReadOnlyJiraClient(config).get_ticket(identifier)
        except Exception:
            typer.echo(
                f"Could not fetch ticket {identifier}: not found or not accessible.", err=True
            )
            raise typer.Exit(code=1) from None
        result = extract_ticket_links(ticket, config.site_url)
    else:
        try:
            page = ReadOnlyConfluenceClient(config).get_page(page_id)
        except Exception:
            typer.echo(
                f"Could not fetch page {identifier}: not found or not accessible.", err=True
            )
            raise typer.Exit(code=1) from None
        result = extract_page_links(page, config.site_url)

    typer.echo(build_links_document(identifier, result))


def _report(product: str, whoami: Callable[[], IdentityCheckResult]) -> bool:
    try:
        result = whoami()
    except Exception as exc:
        typer.echo(f"{product}: FAIL ({exc})")
        return False
    typer.echo(f"{product}: PASS (as {result.display_name})")
    return True
