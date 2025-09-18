"""Main CLI entry point for GPTs Compliance Insights."""

import typer

from gci.cli.commands.action import custom_actions
from gci.cli.commands.download import download_gpts
from gci.cli.commands.list import list_gpts
from gci.cli.commands.risk import risk_classifier

app = typer.Typer(
    name="gci",
    help="GPTs Compliance Insights - Generate reports on GPT configurations",
    add_completion=True,
    rich_markup_mode="rich",
    no_args_is_help=True,
)


@app.callback()
def callback() -> None:
    """
    GPTs Compliance Insights CLI
    """
    pass


app.command("download", help="Download GPTs from the workspace and cache them locally")(download_gpts)
app.command("list", help="List all GPTs in the workspace (uses cached data)")(list_gpts)
app.command("risk-classifier", help="Classify GPT risk levels based on associated file names")(risk_classifier)
app.command("custom-actions", help="Analyze custom actions in GPTs and summarize their capabilities")(custom_actions)


if __name__ == "__main__":
    app()
