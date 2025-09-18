"""TUI mode for listing GPTs with scrollable table."""

import logging
from typing import Any, ClassVar, cast

import pyperclip
from pydantic import BaseModel, Field
from rich.text import Text
from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding, BindingType
from textual.containers import Vertical
from textual.events import Key
from textual.screen import ModalScreen
from textual.widgets import DataTable, Footer, Header, Input, Static, TextArea

from gci.cli.utils.list_shared import COLUMN_CONFIG, GPTDataTransformer, GPTTableRow
from gci.core.highlighting import highlight_text

# Search constants
MIN_SEARCH_LENGTH = 3  # Minimum characters required to trigger search
MAX_SEARCH_RESULTS = 50  # Maximum number of search results to display
MAX_MATCH_HIGHLIGHTS = 5  # Maximum number of match highlights per field

# Preview constants
PREVIEW_MAX_LENGTH = 120  # Maximum length of preview text
PREVIEW_CONTEXT_BEFORE = 40  # Characters to show before match in preview
PREVIEW_CONTEXT_AFTER = 40  # Characters to show after match in preview
SIMPLE_PREVIEW_LENGTH = 100  # Length for simple text preview (no matches)

# Table column constants
MIN_ID_COLUMN_WIDTH = 2  # Minimum width for ID column
ID_COLUMN_PADDING = 2  # Extra padding for ID column width


# All classes and column config are now imported from shared.py

TOTAL_COLUMNS = len(COLUMN_CONFIG)  # Total number of columns in the table

# Modal dialog constants
SEARCH_DIALOG_WIDTH_PERCENT = 90  # Search dialog width as percentage
SEARCH_DIALOG_MAX_WIDTH = 120  # Maximum width for search dialog
SEARCH_DIALOG_HEIGHT_PERCENT = 80  # Search dialog height as percentage
CELL_CONTENT_WIDTH_PERCENT = 80  # Cell content dialog width as percentage
CELL_CONTENT_MAX_WIDTH = 100  # Maximum width for cell content dialog
CELL_CONTENT_HEIGHT_PERCENT = 80  # Cell content dialog height as percentage
CELL_CONTENT_MAX_HEIGHT = 30  # Maximum height for cell content dialog

# UI constants
STATUS_BAR_HEIGHT = 1  # Height of the status bar
ROW_NUMBER_START = 1  # Starting number for row labels
COLUMN_NUMBER_START = 1  # Starting number for column display
HEADER_ROW_INDEX = -1  # Index indicating header row was clicked

# CSS constants
CSS_PADDING = 1  # Standard padding value for CSS
CSS_MARGIN_SINGLE = 1  # Single margin value
CSS_MARGIN_ZERO = 0  # Zero margin value

# Default values
DEFAULT_INDEX = 0  # Default starting index
DEFAULT_COUNT = 0  # Default count value
DEFAULT_TIMESTAMP = 0  # Default timestamp value
EMPTY_COUNT_TEXT = "0"  # Text representation of zero count
NO_USERS_TEXT = "0 users"  # Text for no shared users
NO_FILES_TEXT = "0 files"  # Text for no files

logger = logging.getLogger(__name__)


class SearchResult(BaseModel):
    """Represents a search result."""

    row_index: int = Field(description="Index of the matching row")
    matches: list[tuple[str, str, str]] = Field(description="List of (column_name, preview, full_text) tuples")


class SearchScreen(ModalScreen[int | None]):
    """Modal screen for searching GPTs."""

    CSS = f"""
    SearchScreen {{
        align: center middle;
    }}

    SearchScreen > Vertical {{
        width: {SEARCH_DIALOG_WIDTH_PERCENT}%;
        max-width: {SEARCH_DIALOG_MAX_WIDTH};
        height: {SEARCH_DIALOG_HEIGHT_PERCENT}%;
        background: $surface;
        border: solid $primary;
        padding: {CSS_PADDING};
    }}

    #search-input {{
        margin: {CSS_MARGIN_SINGLE} {CSS_MARGIN_ZERO};
    }}

    #search-results {{
        height: 1fr;
        margin: {CSS_MARGIN_SINGLE} {CSS_MARGIN_ZERO};
        overflow-y: auto;
        overflow-x: hidden;
        border: solid $primary;
        padding: {CSS_PADDING};
        max-width: 100%;
    }}

    .search-result {{
        padding: {CSS_PADDING};
        margin: {CSS_MARGIN_ZERO} {CSS_MARGIN_ZERO} {CSS_MARGIN_SINGLE} {CSS_MARGIN_ZERO};
        border: solid $secondary;
    }}

    .search-result:hover {{
        background: $boost;
    }}
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close", show=False),
    ]

    def __init__(self, table_data: list[GPTTableRow], workspace_id: str, raw_gpts: list[dict[str, Any]]):
        super().__init__()
        self.table_data = table_data
        self.workspace_id = workspace_id
        self.raw_gpts = raw_gpts
        self.column_names = [col.label for col in COLUMN_CONFIG]
        self.search_results: list[SearchResult] = []
        self.selected_row: int | None = None

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("[bold]Search GPTs[/bold]")
            yield Input(placeholder="Enter search term...", id="search-input")
            yield DataTable(id="search-results")
            yield Static("[dim]Press Enter to select, Up/Down to navigate, ESC to close[/dim]")

    def on_mount(self) -> None:
        """Focus on search input when modal opens and setup table."""
        # Setup the search results table (3 columns now)
        table = self.query_one("#search-results", DataTable)
        table.add_column("Row", width=5)
        table.add_column("Name", width=30)
        table.add_column("Match", width=65)
        table.cursor_type = "row"

        self.query_one("#search-input", Input).focus()

    @on(Input.Changed, "#search-input")
    def on_search_changed(self, event: Input.Changed) -> None:
        """Update search results as user types."""
        search_term = event.value.lower()
        table = self.query_one("#search-results", DataTable)

        if len(search_term) >= MIN_SEARCH_LENGTH:  # Minimum characters
            self._perform_search(search_term)
        else:
            # Clear table when search is too short or empty
            self.search_results = []
            table.clear()

    def on_key(self, event: Key) -> None:
        """Handle key events to navigate results while keeping focus on input."""
        table = self.query_one("#search-results", DataTable)
        input_field = self.query_one("#search-input", Input)

        # Handle arrow keys for table navigation while input has focus
        if event.key == "up" and self.search_results:
            event.stop()  # Prevent default input behavior
            if table.cursor_coordinate:
                if table.cursor_coordinate.row > 0:
                    table.move_cursor(row=table.cursor_coordinate.row - 1, animate=True)
                else:
                    # Already at first row, return to search input by ensuring it has focus
                    # This allows the cursor to move within the input text
                    input_field.focus()
        elif event.key == "down" and self.search_results:
            event.stop()  # Prevent default input behavior
            if table.cursor_coordinate and table.cursor_coordinate.row < len(self.search_results) - 1:
                table.move_cursor(row=table.cursor_coordinate.row + 1, animate=True)
        elif event.key == "enter" and self.search_results:
            # Select the current result
            event.stop()
            if table.cursor_coordinate:
                row_idx = table.cursor_coordinate.row
                if row_idx < len(self.search_results):
                    self.selected_row = self.search_results[row_idx].row_index
                    self.dismiss(self.selected_row)

    def _perform_search(self, search_term: str) -> None:
        """Search through all table data using fuzzy search."""
        from gci.core.search import GPTSearcher

        self.search_results = []
        table = self.query_one("#search-results", DataTable)
        table.clear()

        max_results = MAX_SEARCH_RESULTS  # Limit results for performance

        # Use GPTSearcher for fuzzy search
        searcher = GPTSearcher(self.workspace_id)
        search_results = searcher.search_with_highlights(
            search_term,
            self.raw_gpts,
            threshold=80,  # Threshold for full phrase matching with typo tolerance
        )

        # Process results and populate table
        for gpt, score, _patterns in search_results[:max_results]:
            gpt_id = gpt["id"]

            # Find the row index for this GPT
            for row_idx, row_data in enumerate(self.table_data):
                if row_data.gpt_id == gpt_id:
                    self.search_results.append(SearchResult(row_index=row_idx, matches=[]))

                    # Add row to table with 3 columns
                    row_num = f"{row_idx + ROW_NUMBER_START}"
                    name_with_score = f"{row_data.name} ({score:.0f}%)"

                    # Use pre-computed snippet and matched substring from search
                    snippet = gpt.get("_match_snippet", "")
                    matched_substring = gpt.get("_matched_substring", "")

                    # Apply highlighting to the snippet using the actual matched substring
                    if snippet and matched_substring:
                        match_context = highlight_text(snippet, [matched_substring])
                    else:
                        # Fallback if no snippet available
                        match_context = row_data.description[:60] + ("..." if len(row_data.description) > 60 else "")

                    # Add row with 3 columns: row number, name+score, context
                    table.add_row(row_num, name_with_score, match_context)
                    break

        # Move cursor to first result but keep focus on input
        if self.search_results:
            table.move_cursor(row=0, column=0, animate=False)

    @on(DataTable.RowSelected, "#search-results")
    def on_row_selected(self, _event: DataTable.RowSelected) -> None:
        """Handle row selection in search results table."""
        # Get the row key/index from the table cursor
        if self.search_results:
            table = self.query_one("#search-results", DataTable)
            if table.cursor_coordinate:
                row_idx = table.cursor_coordinate.row
                if row_idx < len(self.search_results):
                    self.selected_row = self.search_results[row_idx].row_index
                    self.dismiss(self.selected_row)


class CellContentScreen(ModalScreen[None]):
    """Modal screen to display cell content that can be copied."""

    CSS = f"""
    CellContentScreen {{
        align: center middle;
    }}

    CellContentScreen > Vertical {{
        width: {CELL_CONTENT_WIDTH_PERCENT}%;
        max-width: {CELL_CONTENT_MAX_WIDTH};
        height: {CELL_CONTENT_HEIGHT_PERCENT}%;
        max-height: {CELL_CONTENT_MAX_HEIGHT};
        background: $surface;
        border: solid $primary;
        padding: {CSS_PADDING};
    }}

    #cell-content {{
        height: 1fr;
        margin: {CSS_MARGIN_SINGLE} {CSS_MARGIN_ZERO};
    }}
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("escape", "dismiss", "Close", show=False),
        Binding("ctrl+a", "select_all", "Select All", show=True),
        Binding("ctrl+c", "copy_hint", "Copy", show=True),
    ]

    def __init__(self, content: str, title: str = "Cell Content"):
        super().__init__()
        self.content = content
        self.title = title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"[bold]{self.title}[/bold]\n\n[dim]Text is auto-selected. Press Ctrl+C/Cmd+C to copy:[/dim]")
            text_area = TextArea(self.content, read_only=True)
            text_area.id = "cell-content"
            yield text_area
            yield Static("\n[dim]Press ESC to return to table[/dim]", classes="center")

    def on_mount(self) -> None:
        """Select all text when modal opens."""
        text_area = self.query_one("#cell-content", TextArea)
        text_area.focus()
        # Select all text
        text_area.select_all()

    def action_select_all(self) -> None:
        """Select all text in the text area."""
        text_area = self.query_one("#cell-content", TextArea)
        text_area.select_all()

    def action_copy_hint(self) -> None:
        """Show copy hint."""
        pass  # The binding just shows the user that Ctrl+C is available


class GPTListTUI(App[None]):
    """TUI app for displaying GPTs in an interactive table."""

    CSS = f"""
    DataTable {{
        height: 100%;
    }}

    .status-bar {{
        dock: bottom;
        height: {STATUS_BAR_HEIGHT};
        background: $surface;
        color: $text;
        padding: {CSS_MARGIN_ZERO} {CSS_PADDING};
    }}
    """

    BINDINGS: ClassVar[list[BindingType]] = [
        Binding("q", "quit", "Quit", show=True),
        Binding("escape", "quit", "Quit", show=False),
        Binding("enter", "show_cell", "Show Cell", show=True),
        Binding("c", "copy_cell", "Copy Cell", show=True),
        Binding("s", "sort_current_column", "Sort Column", show=True),
        Binding("/", "focus_search", "Search", show=True),
    ]

    def __init__(
        self,
        gpts_data: list[dict[str, Any]],
        workspace_id: str,
        highlight_patterns_map: dict[str, list[str]] | None = None,
        search_query: str | None = None,
    ):
        super().__init__()
        self.gpts_data = gpts_data
        self.workspace_id = workspace_id
        self.highlight_patterns_map = highlight_patterns_map or {}
        self.search_query = search_query
        self.title = f"GPTs in Workspace {workspace_id}"
        self.raw_table_data: list[GPTTableRow] = []  # Store raw data for copying (immutable after initialization)
        self.current_indices: list[int] = []  # Store current display order as indices into raw_table_data
        self.sort_column: int | None = None  # Currently sorted column
        self.sort_reverse: bool = False  # Sort direction
        self.column_keys: list[str] = []  # Store column keys for sorting
        self.data_transformer = GPTDataTransformer()  # Create instance of data transformer

    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        yield DataTable()
        yield Static(
            f"Total GPTs: {len(self.gpts_data)} | Click headers to sort | Press 's' to sort, '/' to search",
            classes="status-bar",
        )
        yield Footer()

    def on_mount(self) -> None:
        """Set up the data table when the app starts."""
        table = self.query_one(DataTable)

        # Enable row labels for numbering
        table.show_row_labels = True
        # Note: row_label_width may not be available in all Textual versions

        # First pass: calculate maximum ID length
        max_id_length = MIN_ID_COLUMN_WIDTH  # Minimum for "ID" header
        for gpt in self.gpts_data:
            gpt_id = str(gpt.get("id", ""))
            if gpt_id:
                max_id_length = max(max_id_length, len(gpt_id))

        # Add padding for readability
        id_column_width = max_id_length + ID_COLUMN_PADDING

        # Add columns using centralized configuration
        for col_config in COLUMN_CONFIG:
            key = col_config.key
            label = col_config.label
            width = col_config.width

            # Special handling for ID column with dynamic width
            if key == "id":
                width = id_column_width

            table.add_column(label, width=width, key=key)
            self.column_keys.append(key)

        # Add rows and initialize raw_table_data (only done once)
        for gpt in self.gpts_data:
            row_data = self.data_transformer.extract_gpt_fields(gpt, format_for_tui=True)
            # Store raw data for copying (immutable after this)
            self.raw_table_data.append(row_data)

        # Initialize current indices to natural order
        self.current_indices = list(range(len(self.raw_table_data)))

        # Add rows to table using current indices
        for display_idx, actual_idx in enumerate(self.current_indices, ROW_NUMBER_START):
            row_data = self.raw_table_data[actual_idx]
            row_tuple = row_data.to_tuple()
            # Apply highlighting if highlight patterns exist for this GPT
            patterns = self.highlight_patterns_map.get(row_data.gpt_id, [])
            if patterns:
                row_tuple = self._apply_highlighting_to_row(row_tuple, patterns)
            table.add_row(*row_tuple, label=str(display_idx))

        # Focus on the table
        table.focus()

    def _apply_highlighting_to_row(self, row: tuple[Any, ...], patterns: list[str]) -> tuple[Any, ...]:
        """Apply highlighting to row data using unified highlighting."""
        return tuple(highlight_text(str(field), patterns) if isinstance(field, str) else field for field in row)

    @on(DataTable.CellHighlighted)
    def on_cell_highlighted(self, event: DataTable.CellHighlighted) -> None:
        """Update status bar when cell is highlighted."""
        status_bar = self.query_one(".status-bar", Static)
        sort_info = ""
        if self.sort_column is not None:
            sort_info = f" | Sorted by: {self.column_keys[self.sort_column]} {'↓' if self.sort_reverse else '↑'}"
        else:
            sort_info = " | Unsorted (original order)"
        status_bar.update(
            f"Total GPTs: {len(self.gpts_data)} | "
            f"Row: {event.coordinate.row + ROW_NUMBER_START}/{len(self.gpts_data)} | "
            f"Column: {event.coordinate.column + COLUMN_NUMBER_START}/{TOTAL_COLUMNS}{sort_info}"
        )

    @on(DataTable.CellSelected)
    def on_cell_selected(self, event: DataTable.CellSelected) -> None:
        """Handle cell selection, including header clicks for sorting."""
        # Check if header row was clicked
        if event.coordinate.row == HEADER_ROW_INDEX:  # Header row
            self._sort_by_column(event.coordinate.column)
        else:
            # For non-header cells, show the cell content
            self.action_show_cell()

    def action_show_cell(self) -> None:
        """Show the current cell content in a modal for copying."""
        table = self.query_one(DataTable)
        row = table.cursor_coordinate.row
        col = table.cursor_coordinate.column

        # Get actual row index from current_indices
        if row < len(self.current_indices) and col < len(COLUMN_CONFIG):
            actual_row_idx = self.current_indices[row]
            row_data = self.raw_table_data[actual_row_idx]
            content = row_data.get_field_value_by_index(col)
            title = f"{COLUMN_CONFIG[col].label} (Row {row + ROW_NUMBER_START})"
            self.push_screen(CellContentScreen(content, title))

    def action_copy_cell(self) -> None:
        """Copy the current cell content to clipboard."""
        table = self.query_one(DataTable)
        row = table.cursor_coordinate.row
        col = table.cursor_coordinate.column

        # Get actual row index from current_indices
        if row < len(self.current_indices) and col < len(COLUMN_CONFIG):
            actual_row_idx = self.current_indices[row]
            row_data = self.raw_table_data[actual_row_idx]
            content = row_data.get_field_value_by_index(col)
            try:
                pyperclip.copy(content)
                # Update status bar to show copy success
                status_bar = self.query_one(".status-bar", Static)
                status_bar.update(
                    f"Total GPTs: {len(self.gpts_data)} | "
                    f"Row: {row + ROW_NUMBER_START}/{len(self.gpts_data)} | "
                    f"Column: {col + COLUMN_NUMBER_START}/{TOTAL_COLUMNS} | "
                    "[green]Copied to clipboard![/green]"
                )
            except Exception:
                # If pyperclip fails, show error message
                status_bar = self.query_one(".status-bar", Static)
                status_bar.update(
                    f"Total GPTs: {len(self.gpts_data)} | "
                    f"Row: {row + ROW_NUMBER_START}/{len(self.gpts_data)} | "
                    f"Column: {col + COLUMN_NUMBER_START}/{TOTAL_COLUMNS} | "
                    "[red]Copy failed - clipboard not available[/red]"
                )

    def action_sort_current_column(self) -> None:
        """Sort by the current column using keyboard shortcut."""
        table = self.query_one(DataTable)
        # Sort by the current column
        self._sort_by_column(table.cursor_coordinate.column)

    def action_focus_search(self) -> None:
        """Open search modal."""
        search_modal = SearchScreen(self.raw_table_data, self.workspace_id, self.gpts_data)

        def handle_search_result(result: int | None) -> None:
            """Handle the search result selection."""
            if result is not None:
                # Find the display row for this actual row index
                table = self.query_one(DataTable)
                for display_idx, actual_idx in enumerate(self.current_indices):
                    if actual_idx == result:
                        # Move cursor to the found row
                        table.move_cursor(row=display_idx, column=0, animate=False)

                        # Scroll to show the row with 2-3 rows above it for context
                        target_scroll = max(0, display_idx - 3)
                        table.scroll_to(y=target_scroll, animate=False)
                        break
                # Focus back on the table
                table.focus()

        self.push_screen(search_modal, handle_search_result)

    def _extract_date_sort_key(self, value: Any) -> int:
        """Extract sort key from date value (expecting YYYY-MM-DD format)."""
        if not value:
            return DEFAULT_TIMESTAMP

        # For date strings in YYYY-MM-DD format
        from datetime import datetime

        try:
            return int(datetime.strptime(str(value), "%Y-%m-%d").timestamp())
        except ValueError as e:
            logger.debug(f"Failed to parse date for sorting '{value}': {e}")
            return DEFAULT_TIMESTAMP

    def _extract_count_sort_key(self, value: Any, pattern: str) -> int:
        """Extract numeric count from strings like '3 files' or '5 users'."""
        value_str = str(value)
        if pattern not in value_str:
            return DEFAULT_COUNT

        # Get first word and convert to int if possible
        first_word = value_str.split()[DEFAULT_INDEX] if value_str else EMPTY_COUNT_TEXT
        return int(first_word) if first_word.isdigit() else 0

    def _get_string_sort_key(self, value: Any) -> str:
        """Extract string sort key by converting to lowercase."""
        return str(value).lower() if value else ""

    def _get_sort_value_by_column(self, row_index: int, column: int) -> Any:
        """Get the sort value for a specific row and column.

        Args:
            row_index: Index into raw_table_data
            column: Column index

        Returns:
            The value to use for sorting
        """
        row_data = self.raw_table_data[row_index]
        value = row_data.get_field_value_by_index(column)

        # Get sort type from column configuration
        col_config = COLUMN_CONFIG[column]
        sort_type = col_config.sort_type

        if sort_type == "date":
            return self._extract_date_sort_key(value)
        elif sort_type == "count":
            # Determine pattern based on column key
            column_key = self.column_keys[column]
            pattern = "files" if column_key == "files" else "user"
            return self._extract_count_sort_key(value, pattern)
        else:  # Default to string sort
            return self._get_string_sort_key(value)

    def _sort_by_column(self, column: int) -> None:
        """Sort the table by the selected column."""
        table = self.query_one(DataTable)

        # Remember current cursor position using actual data index
        cursor_coordinate = table.cursor_coordinate
        current_row_actual_idx = None
        if cursor_coordinate and cursor_coordinate.row < len(self.current_indices):
            current_row_actual_idx = self.current_indices[cursor_coordinate.row]

        # Handle three-state sorting: ascending -> descending -> unsorted
        if self.sort_column == column:
            if not self.sort_reverse:
                # Currently ascending, switch to descending
                self.sort_reverse = True
            else:
                # Currently descending, clear sort
                self.sort_column = None
                self.sort_reverse = False
                # Restore original order by resetting indices
                self.current_indices = list(range(len(self.raw_table_data)))

                # Clear and repopulate table with original order
                table.clear()
                for display_idx, actual_idx in enumerate(self.current_indices, ROW_NUMBER_START):
                    row_data = self.raw_table_data[actual_idx]
                    row_tuple = row_data.to_tuple()
                    # Apply highlighting if patterns exist for this GPT
                    patterns = self.highlight_patterns_map.get(row_data.gpt_id, [])
                    if patterns:
                        row_tuple = self._apply_highlighting_to_row(row_tuple, patterns)
                    table.add_row(*row_tuple, label=str(display_idx))

                # Clear all sort indicators
                for col_idx, col_config in enumerate(COLUMN_CONFIG):
                    col_key = self.column_keys[col_idx]
                    label = col_config.label
                    table.columns[cast("Any", col_key)].label = Text(label)

                # Restore cursor position
                if current_row_actual_idx is not None and cursor_coordinate:
                    # Find where the original row is now displayed
                    for display_idx, actual_idx in enumerate(self.current_indices):
                        if actual_idx == current_row_actual_idx:
                            table.move_cursor(row=display_idx, column=cursor_coordinate.column, animate=False)
                            break
                return
        else:
            # New column, start with ascending
            self.sort_column = column
            self.sort_reverse = False

        # Sort the current indices based on the data they point to
        self.current_indices.sort(
            key=lambda idx: self._get_sort_value_by_column(idx, column), reverse=self.sort_reverse
        )

        # Clear and repopulate the table with sorted data
        table.clear()

        for display_idx, actual_idx in enumerate(self.current_indices, ROW_NUMBER_START):
            row_data = self.raw_table_data[actual_idx]
            row_tuple = row_data.to_tuple()
            # Apply highlighting if patterns exist for this GPT
            patterns = self.highlight_patterns_map.get(row_data.gpt_id, [])
            if patterns:
                row_tuple = self._apply_highlighting_to_row(row_tuple, patterns)
            table.add_row(*row_tuple, label=str(display_idx))

        # Update column headers to show sort indicator
        for i, col_config in enumerate(COLUMN_CONFIG):
            col_key = self.column_keys[i]
            label = col_config.label

            if i == column:
                # Add sort indicator to current column
                indicator = " ↓" if self.sort_reverse else " ↑"
                table.columns[cast("Any", col_key)].label = Text(label + indicator)
            else:
                # Remove sort indicator from other columns
                table.columns[cast("Any", col_key)].label = Text(label)

        # Restore cursor position
        if current_row_actual_idx is not None and cursor_coordinate:
            # Find where the original row is now displayed
            for display_idx, actual_idx in enumerate(self.current_indices):
                if actual_idx == current_row_actual_idx:
                    # Move cursor to the same data at its new position
                    table.move_cursor(row=display_idx, column=cursor_coordinate.column, animate=False)
                    break


def launch_gpt_list_tui(
    gpts_data: list[dict[str, Any]],
    workspace_id: str,
    highlight_patterns_map: dict[str, list[str]] | None = None,
    search_query: str | None = None,
) -> None:
    """Launch the TUI app for displaying GPTs."""
    app = GPTListTUI(gpts_data, workspace_id, highlight_patterns_map, search_query)
    app.run()
