"""List GPTs command implementation."""

import csv
import io
import json
import logging
import time
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import dateparser
import typer
from rich.console import Console
from rich.table import Table

from gci.cli.commands.list_tui import launch_gpt_list_tui
from gci.cli.utils.auth import get_api_credentials
from gci.cli.utils.data import load_cached_gpts
from gci.cli.utils.list_shared import COLUMN_CONFIG, GPTDataTransformer
from gci.core.constants import FormattingConstants
from gci.core.highlighting import highlight_text
from gci.models.stats import ListCommandStats

console = Console()
logger = logging.getLogger(__name__)


# Removed highlight_matches - now using unified gci.highlighting.highlight_text


def _list_gpts(workspace_id: str, no_download: bool, stats: ListCommandStats) -> list[dict[str, Any]]:
    # Try to load from cache first
    cache_result = load_cached_gpts(
        workspace_id,
        force_fresh=False,
        auto_accept=True,  # Auto-accept cache for list command
    )

    stats.from_cache = cache_result.used_cache

    if cache_result.data:
        stats.gpts_found = len(cache_result.data)
        return cache_result.data

    # No cached data available
    if no_download:
        console.print("[yellow]No cached data found.[/yellow]")
        console.print("[dim]Use 'gci download' to fetch GPT data first.[/dim]")
        return []
    else:
        console.print("[yellow]No cached data found.[/yellow]")
        console.print("[bold]Please run 'gci download' first to fetch GPT data.[/bold]")
        console.print(f"\n[dim]Example: gci download --workspace-id {workspace_id}[/dim]")
        raise typer.Exit(1)


class OutputFormat(StrEnum):
    """Available output formats for list-gpts command."""

    table = "table"
    json = "json"
    csv = "csv"


def handle_table_output(
    gpts_data: list[dict[str, Any]], workspace_id: str, highlight_patterns_map: dict[str, list[str]]
) -> None:
    """Handle table format output."""
    table = Table(title=f"GPTs in Workspace {workspace_id}", show_lines=True, expand=True)
    # Add columns using COLUMN_CONFIG with styles from configuration
    for col_config in COLUMN_CONFIG:
        # Use get_table_kwargs() method from column config
        kwargs = col_config.get_table_kwargs()
        table.add_column(col_config.label, **kwargs)

    # Initialize data transformer
    data_transformer = GPTDataTransformer()

    for gpt in gpts_data:
        # Extract all fields using shared transformer
        row_data = data_transformer.extract_gpt_fields(gpt, format_for_tui=False)

        # Get GPT ID for highlighting patterns
        gpt_id = row_data.gpt_id

        # Apply highlighting if search was used
        patterns = highlight_patterns_map.get(gpt_id, [])
        if patterns:
            # Convert to tuple and apply highlighting to each field
            row_tuple = row_data.to_tuple()
            highlighted_row = tuple(highlight_text(field, patterns) for field in row_tuple)
            table.add_row(*highlighted_row)
        else:
            # Add row without highlighting
            table.add_row(*row_data.to_tuple())

    # Print table
    console.print(table)
    console.print(f"\n[bold]Total GPTs:[/bold] {len(gpts_data)}")


def handle_json_output(gpts_data: list[dict[str, Any]], output_path: Path | None) -> None:
    """Handle JSON format output."""
    json_content = json.dumps(gpts_data, indent=FormattingConstants.JSON_INDENT, default=str)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_content, encoding="utf-8")
        console.print(f"[bold green]✓ Saved to:[/bold green] {output_path}")
    else:
        print(json_content)


def handle_csv_output(gpts_data: list[dict[str, Any]], output_path: Path | None) -> None:
    """Handle CSV format output."""
    string_buffer = io.StringIO()
    if gpts_data:
        # Get all unique keys from all GPTs to ensure we have all columns
        all_keys = set()
        for gpt in gpts_data:
            all_keys.update(gpt.keys())

        # Sort keys for consistent output
        fieldnames = sorted(all_keys)

        writer = csv.DictWriter(string_buffer, fieldnames=fieldnames)
        writer.writeheader()

        for gpt in gpts_data:
            # Flatten nested objects for CSV
            row = {}
            for key, value in gpt.items():
                if isinstance(value, dict | list):
                    row[key] = json.dumps(value, default=str)
                else:
                    row[key] = str(value) if value is not None else ""
            writer.writerow(row)

    csv_content = string_buffer.getvalue()
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(csv_content, encoding="utf-8")
        console.print(f"[bold green]✓ Saved to:[/bold green] {output_path}")
    else:
        print(csv_content)


def list_gpts(
    workspace_id: Annotated[
        str | None,
        typer.Option(
            "--workspace-id",
            "-w",
            help="OpenAI workspace ID (auto-detected from GCI_OPENAI_WORKSPACE_ID env var)",
        ),
    ] = None,
    output_format: Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format",
            case_sensitive=False,
        ),
    ] = OutputFormat.table,
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="Output file path (required for json/csv formats unless you want to be prompted)",
        ),
    ] = None,
    no_download: Annotated[
        bool,
        typer.Option(
            "--no-download",
            help="Only use cached data, don't download if cache is missing",
        ),
    ] = False,
    no_tui: Annotated[
        bool,
        typer.Option(
            "--no-tui",
            help="Disable TUI and use simple table output. In TUI mode, click column headers to sort.",
        ),
    ] = False,
    search: Annotated[
        str | None,
        typer.Option(
            "--search",
            help="Search filter (regex pattern)",
        ),
    ] = None,
    created_after: Annotated[
        str | None,
        typer.Option(
            "--created-after",
            help="Filter GPTs created after this date (e.g., '2024-01-01', 'yesterday', '1 week ago')",
        ),
    ] = None,
    created_before: Annotated[
        str | None,
        typer.Option(
            "--created-before",
            help="Filter GPTs created before this date (e.g., '2024-12-31', 'today', '1 month ago')",
        ),
    ] = None,
) -> None:
    """List all GPTs in the workspace with their configurations and shared users.

    By default, this command uses cached data if available. To download fresh data,
    use the 'gci download' command first.
    """

    # Track statistics
    stats = ListCommandStats(start_time=time.time(), gpts_found=0, from_cache=False)

    _, workspace_id = get_api_credentials(workspace_id=workspace_id)

    # Run the function
    gpts_data = _list_gpts(workspace_id, no_download, stats)

    # Show stats
    elapsed = time.time() - stats.start_time
    if stats.from_cache:
        console.print(f"\n[dim]Loaded from cache in {elapsed:.1f}s[/dim]")
    else:
        console.print(f"\n[dim]Completed in {elapsed:.1f}s[/dim]")

    if not gpts_data:
        console.print("[yellow]No GPTs found in workspace[/yellow]")
        return

    # Apply all filters at once using GPTSearcher
    highlight_patterns_map = {}  # Map GPT ID to highlight patterns

    if search or created_after or created_before:
        from gci.core.search import GPTSearcher

        # Validate date formats first
        if created_after and not dateparser.parse(created_after):
            console.print(f"[red]Invalid date format for --created-after: {created_after}[/red]")
            raise typer.Exit(1)

        if created_before and not dateparser.parse(created_before):
            console.print(f"[red]Invalid date format for --created-before: {created_before}[/red]")
            raise typer.Exit(1)

        searcher = GPTSearcher(workspace_id)

        if search:
            # Use search_with_highlights for fuzzy search
            search_results = searcher.search_with_highlights(search, gpts_data, threshold=80)

            # Extract GPTs and patterns
            gpts_data = []
            for gpt, _score, patterns in search_results:
                gpts_data.append(gpt)
                highlight_patterns_map[gpt["id"]] = patterns

            stats.filtered_count = len(gpts_data)
            stats.search_pattern = search
        else:
            # Just date filtering
            gpts_data = searcher.filter_and_search(
                gpts_data,
                created_after=created_after,
                created_before=created_before,
            )

        console.print(f"[dim]Filtered to {len(gpts_data)} GPTs[/dim]")

    # Handle output file for non-table formats
    if output_format != OutputFormat.table and not output:
        # Prompt user for output file
        default_extension = "json" if output_format == OutputFormat.json else "csv"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"gpts_{timestamp}.{default_extension}"

        console.print(f"\n[yellow]No output file specified for {output_format.value} format.[/yellow]")
        output_path = typer.prompt("Enter output filename", default=default_filename, show_default=True)
        output = Path(output_path)

    # Display results using appropriate handler
    if output_format == OutputFormat.table and not no_tui:
        # Launch TUI mode (default for table format)
        launch_gpt_list_tui(gpts_data, workspace_id, highlight_patterns_map, search)
    elif output_format == OutputFormat.table:
        handle_table_output(gpts_data, workspace_id, highlight_patterns_map)
    elif output_format == OutputFormat.json:
        handle_json_output(gpts_data, output)
    elif output_format == OutputFormat.csv:
        handle_csv_output(gpts_data, output)
