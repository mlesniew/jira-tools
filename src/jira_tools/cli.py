import typer

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
