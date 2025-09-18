"""Shared CLI options and enums for commands."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Any

import typer


class OutputFormat(StrEnum):
    """Supported output formats across commands."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"
    TUI = "tui"  # Only for list command


# Common typer options
WORKSPACE_ID_OPTION = Annotated[
    str | None,
    typer.Option(
        "--workspace-id",
        "-w",
        help="OpenAI workspace ID (auto-detected from GCI_OPENAI_WORKSPACE_ID env var)",
    ),
]

OUTPUT_PATH_OPTION = Annotated[
    Path | None,
    typer.Option(
        "--output",
        "-o",
        help="Output file path (required for json/csv formats unless output to stdout)",
    ),
]

OUTPUT_FORMAT_OPTION = Annotated[
    OutputFormat,
    typer.Option(
        "--format",
        "-f",
        help="Output format",
        case_sensitive=False,
    ),
]

NO_DOWNLOAD_OPTION = Annotated[
    bool,
    typer.Option(
        "--no-download",
        help="Only use cached data, don't download if cache is missing",
    ),
]

SEARCH_OPTION = Annotated[
    str | None,
    typer.Option(
        "--search",
        help="Search filter (regex pattern or fuzzy search)",
    ),
]

API_KEY_OPTION = Annotated[
    str | None,
    typer.Option(
        "--api-key",
        "-k",
        help="API key (auto-detected from environment)",
        hide_input=True,
    ),
]

FORCE_OPTION = Annotated[
    bool,
    typer.Option(
        "--force",
        "-f",
        help="Force operation (e.g., fresh download, skip cache)",
    ),
]

VERBOSE_OPTION = Annotated[
    bool,
    typer.Option(
        "--verbose",
        "-v",
        help="Enable verbose output",
    ),
]


def get_output_format_option(
    default: OutputFormat = OutputFormat.TABLE,  # noqa: ARG001
    include_tui: bool = False,
) -> Any:
    """Get output format option with customizable default and TUI inclusion.

    Args:
        default: Default output format
        include_tui: Whether to include TUI as a valid option

    Returns:
        Annotated type for use in typer commands
    """
    valid_formats = [OutputFormat.TABLE, OutputFormat.JSON, OutputFormat.CSV]
    if include_tui:
        valid_formats.append(OutputFormat.TUI)

    help_text = f"Output format ({', '.join(f.value for f in valid_formats)})"

    return Annotated[
        OutputFormat,
        typer.Option(
            "--format",
            "-f",
            help=help_text,
            case_sensitive=False,
        ),
    ]
