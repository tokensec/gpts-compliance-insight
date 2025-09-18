"""Shared output handlers for CLI commands."""

import csv
import io
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from rich.console import Console

from gci.core.constants import FormattingConstants

console = Console()


def handle_json_output(
    data: Any,
    output_path: Path | None,
    transformer: Callable[[Any], dict[str, Any]] | None = None,
) -> None:
    """Handle JSON format output.

    Args:
        data: Data to output (can be any type)
        output_path: Optional file path to save output
        transformer: Optional function to transform data before serialization
    """
    # Transform data if transformer provided
    output_data = transformer(data) if transformer else data

    # Serialize to JSON
    json_content = json.dumps(output_data, indent=FormattingConstants.JSON_INDENT, default=str)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json_content, encoding="utf-8")
        console.print(f"[bold green]✓ Saved to:[/bold green] {output_path}")
    else:
        print(json_content)


def handle_csv_output(
    data: Any,
    output_path: Path | None,
    fieldnames: list[str] | None = None,
    row_transformer: Callable[[Any], dict[str, Any]] | None = None,
) -> None:
    """Handle CSV format output.

    Args:
        data: Data to output (list of items or single item)
        output_path: Optional file path to save output
        fieldnames: Optional list of field names for CSV header
        row_transformer: Optional function to transform each row before writing
    """
    string_buffer = io.StringIO()

    # Ensure data is a list
    items = data if isinstance(data, list) else [data]

    if items:
        # Determine fieldnames if not provided
        if not fieldnames:
            if row_transformer:
                # Get fieldnames from transformed first item
                first_row = row_transformer(items[0])
                fieldnames = list(first_row.keys())
            elif isinstance(items[0], dict):
                # Get all unique keys from all items
                all_keys = set()
                for item in items:
                    all_keys.update(item.keys())
                fieldnames = sorted(all_keys)
            else:
                # Try to get fieldnames from object attributes
                first_item = items[0]
                if hasattr(first_item, "__dict__"):
                    fieldnames = sorted(first_item.__dict__.keys())
                else:
                    raise ValueError("Cannot determine fieldnames for CSV output")

        writer = csv.DictWriter(string_buffer, fieldnames=fieldnames)
        writer.writeheader()

        for item in items:
            # Transform row if transformer provided
            if row_transformer:
                row = row_transformer(item)
            elif isinstance(item, dict):
                # Flatten nested objects for CSV
                row = {}
                for key, value in item.items():
                    if isinstance(value, dict | list):
                        row[key] = json.dumps(value, default=str)
                    else:
                        row[key] = "" if cast(Any, value) is None else str(value)
            else:
                # Convert object to dict
                if hasattr(item, "model_dump"):
                    # Pydantic model
                    row = item.model_dump()
                elif hasattr(item, "__dict__"):
                    row = item.__dict__
                else:
                    row = {"value": str(item)}

                # Flatten nested values
                for key, value in list(row.items()):
                    if isinstance(value, dict | list):
                        row[key] = json.dumps(value, default=str)
                    else:
                        # Cast to Any to handle potential None values from object dictionaries
                        row[key] = "" if cast(Any, value) is None else str(value)

            writer.writerow(row)

    csv_content = string_buffer.getvalue()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(csv_content, encoding="utf-8")
        console.print(f"[bold green]✓ Saved to:[/bold green] {output_path}")
    else:
        print(csv_content)
