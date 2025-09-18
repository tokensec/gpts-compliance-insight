"""CLI utilities module."""

from gci.cli.utils.auth import get_api_credentials
from gci.cli.utils.data import load_cached_gpts
from gci.cli.utils.options import (
    NO_DOWNLOAD_OPTION,
    OUTPUT_FORMAT_OPTION,
    OUTPUT_PATH_OPTION,
    SEARCH_OPTION,
    WORKSPACE_ID_OPTION,
    OutputFormat,
    get_output_format_option,
)
from gci.cli.utils.output import handle_csv_output, handle_json_output

__all__ = [
    "NO_DOWNLOAD_OPTION",
    "OUTPUT_FORMAT_OPTION",
    "OUTPUT_PATH_OPTION",
    "SEARCH_OPTION",
    "WORKSPACE_ID_OPTION",
    "OutputFormat",
    "get_api_credentials",
    "get_output_format_option",
    "handle_csv_output",
    "handle_json_output",
    "load_cached_gpts",
]
