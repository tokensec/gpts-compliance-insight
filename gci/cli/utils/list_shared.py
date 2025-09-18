"""Shared components for list_gpts command."""

import logging
from datetime import datetime
from typing import Any

import dateparser
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class ColumnDefinition(BaseModel):
    """Configuration for a table column."""

    key: str = Field(description="Unique key for the column")
    label: str = Field(description="Display label for the column header")
    width: int | None = Field(default=None, description="Column width (None for dynamic)")
    sort_type: str = Field(default="string", description="Type of sorting: string, date, or count")
    # Rich table styling options
    style: str | None = Field(default=None, description="Rich text style for the column")
    no_wrap: bool = Field(default=False, description="Prevent text wrapping")
    overflow: str | None = Field(default=None, description="Text overflow handling: fold, crop, ellipsis")
    min_width: int | None = Field(default=None, description="Minimum column width")
    max_width: int | None = Field(default=None, description="Maximum column width")

    def get_table_kwargs(self) -> dict[str, Any]:
        """Get kwargs for Rich table.add_column(), excluding None values and defaults."""
        kwargs = {}

        # Add only non-None/non-default values
        if self.style:
            kwargs["style"] = self.style
        if self.width:
            kwargs["width"] = self.width
        # Always include no_wrap since it has a boolean default
        kwargs["no_wrap"] = self.no_wrap
        if self.overflow:
            kwargs["overflow"] = self.overflow
        if self.min_width:
            kwargs["min_width"] = self.min_width
        if self.max_width:
            kwargs["max_width"] = self.max_width

        return kwargs


# Centralized column configuration used by both table and TUI modes
COLUMN_CONFIG = [
    ColumnDefinition(key="id", label="ID", width=38, sort_type="string", style="cyan", no_wrap=True),
    ColumnDefinition(
        key="name", label="Name", width=20, sort_type="string", style="magenta", overflow="fold", min_width=25
    ),
    ColumnDefinition(
        key="description",
        label="Description",
        width=40,
        sort_type="string",
        style="white",
        overflow="fold",
        min_width=30,
    ),
    ColumnDefinition(
        key="owner", label="Owner", width=25, sort_type="string", style="green", overflow="fold", max_width=25
    ),
    ColumnDefinition(key="created", label="Created", width=12, sort_type="date", style="dim", no_wrap=False),
    ColumnDefinition(
        key="instructions",
        label="Instructions",
        width=40,
        sort_type="string",
        style="yellow",
        overflow="fold",
        min_width=35,
    ),
    ColumnDefinition(key="categories", label="Categories", width=15, sort_type="string", style="blue", no_wrap=True),
    ColumnDefinition(key="sharing", label="Sharing", width=15, sort_type="string", style="red", no_wrap=True),
    ColumnDefinition(
        key="shared_with",
        label="Shared With",
        width=25,
        sort_type="count",
        style="green",
        overflow="fold",
        max_width=20,
    ),
    ColumnDefinition(
        key="starters", label="Starters", width=30, sort_type="string", style="cyan", overflow="fold", max_width=25
    ),
    ColumnDefinition(
        key="tools", label="Tools", width=30, sort_type="string", style="magenta", overflow="fold", max_width=25
    ),
    ColumnDefinition(
        key="files", label="Files", width=30, sort_type="count", style="dim", overflow="fold", max_width=25
    ),
]


class GPTTableRow(BaseModel):
    """Represents a row of GPT data for table display."""

    gpt_id: str = Field(description="GPT identifier")
    name: str = Field(description="GPT name")
    description: str = Field(description="GPT description")
    owner_info: str = Field(description="Owner/builder information")
    created_at: str = Field(description="Creation date (formatted)")
    instructions: str = Field(description="GPT instructions")
    categories: str = Field(description="Categories (comma-separated)")
    sharing_visibility: str = Field(description="Sharing visibility setting")
    shared_with_info: str = Field(description="Shared users information")
    conversation_starters: str = Field(description="Conversation starters (semicolon-separated)")
    tools: str = Field(description="Tools information (comma-separated)")
    files_info: str = Field(description="Files information with count")

    def to_tuple(self) -> tuple[str, ...]:
        """Convert to tuple for table display."""
        return (
            self.gpt_id,
            self.name,
            self.description,
            self.owner_info,
            self.created_at,
            self.instructions,
            self.categories,
            self.sharing_visibility,
            self.shared_with_info,
            self.conversation_starters,
            self.tools,
            self.files_info,
        )

    def get_field_value_by_index(self, index: int) -> str:
        """Get field value by column index."""
        # Map column index to field name based on COLUMN_CONFIG order
        field_mapping = [
            self.gpt_id,  # 0: id
            self.name,  # 1: name
            self.description,  # 2: description
            self.owner_info,  # 3: owner
            self.created_at,  # 4: created
            self.instructions,  # 5: instructions
            self.categories,  # 6: categories
            self.sharing_visibility,  # 7: sharing
            self.shared_with_info,  # 8: shared_with
            self.conversation_starters,  # 9: starters
            self.tools,  # 10: tools
            self.files_info,  # 11: files
        ]
        return field_mapping[index] if 0 <= index < len(field_mapping) else ""

    @classmethod
    def get_field_by_index(cls, index: int) -> str | None:
        """Get field name by index (for accessing data)."""
        fields = list(cls.model_fields.keys())
        return fields[index] if 0 <= index < len(fields) else None


class GPTDataTransformer:
    """Handles data transformation for GPT objects."""

    def get_latest_config(self, gpt: dict[str, Any]) -> dict[str, Any] | None:
        """Extract the latest configuration data from GPT."""
        if not gpt.get("latest_config"):
            return None

        config = gpt["latest_config"]
        if "data" in config and config["data"] and len(config["data"]) > 0:
            return config["data"][0]
        return None

    def extract_basic_info(self, config: dict[str, Any] | None) -> tuple[str, str, str]:
        """Extract name, description, and instructions from config."""
        if not config:
            return "Unnamed", "", ""

        name = str(config.get("name", "Unnamed"))
        description = str(config.get("description", ""))
        instructions = str(config.get("instructions", ""))

        return name, description, instructions

    def extract_categories(self, config: dict[str, Any] | None) -> str:
        """Extract categories from config."""
        if not config:
            return ""

        categories_list = config.get("categories", [])
        return ", ".join(categories_list) if categories_list else ""

    def extract_conversation_starters(self, config: dict[str, Any] | None) -> str:
        """Extract conversation starters from config."""
        if not config:
            return ""

        starters_list = config.get("conversation_starters", [])
        return "; ".join(starters_list) if starters_list else ""

    def extract_tools_info(self, config: dict[str, Any] | None) -> str:
        """Extract tools information from config."""
        if not config:
            return ""

        tools_data = config.get("tools", {})
        if tools_data.get("data"):
            tools_list = [t.get("type", "") for t in tools_data["data"] if t.get("type")]
            return ", ".join(tools_list)
        return ""

    def extract_files_info(self, config: dict[str, Any] | None, numbered_list: bool = False) -> str:
        """Extract files information.

        Args:
            config: GPT configuration data
            numbered_list: If True, format as numbered list (for TUI), otherwise comma-separated (for table)
        """
        if not config:
            return "0 files"

        files_data = config.get("files", {})
        if not files_data.get("data"):
            return "0 files"

        files_list = [f.get("name", "") for f in files_data["data"] if f.get("name")]
        if not files_list:
            return "0 files"

        if numbered_list:
            # Format as a numbered list with line breaks (for TUI)
            files_formatted = [f"{i + 1}. {name}" for i, name in enumerate(files_list)]
            return f"{len(files_list)} files:\n" + "\n".join(files_formatted)
        else:
            # Format as comma-separated list (for table)
            return f"{len(files_list)} files: " + ", ".join(files_list)

    def extract_owner_info(self, gpt: dict[str, Any], format_for_tui: bool = False) -> str:
        """Extract owner/builder information.

        Args:
            gpt: GPT data dictionary
            format_for_tui: If True, format as "name (email)", otherwise as "name\\nemail" for table
        """
        builder = str(gpt.get("builder_name", "Unknown"))
        owner_email = str(gpt.get("owner_email", ""))

        # Combine builder name and email
        if owner_email and builder != "Unknown":
            if format_for_tui:
                return f"{builder} ({owner_email})"
            else:
                return f"{builder}\n{owner_email}"
        elif owner_email:
            return owner_email
        else:
            return builder

    def extract_sharing_info(self, gpt: dict[str, Any]) -> tuple[str, str]:
        """Extract sharing visibility and shared users information."""
        sharing_data = gpt.get("sharing", {})
        sharing_visibility = sharing_data.get("visibility", "unknown")

        # Shared with users
        recipients_data = sharing_data.get("recipients", {})
        shared_users = []
        if recipients_data.get("data"):
            for recipient in recipients_data["data"]:
                email = recipient.get("email", "")
                if email:
                    shared_users.append(email)

        # Format shared users info
        shared_with_info = f"{len(shared_users)} users: {', '.join(shared_users)}" if shared_users else "0 users"

        return sharing_visibility, shared_with_info

    def format_created_date(self, created_at: Any) -> str:
        """Format the creation date to human-readable format."""
        if not created_at:
            return ""

        try:
            # dateparser handles Unix timestamps, ISO strings, and datetime objects
            if isinstance(created_at, int | float):
                # Unix timestamp
                dt = datetime.fromtimestamp(created_at)
            else:
                # Let dateparser handle various string formats
                dt = dateparser.parse(str(created_at))

            return dt.strftime("%Y-%m-%d") if dt else str(created_at)
        except (ValueError, TypeError, AttributeError) as e:
            # Fallback to original if parsing fails
            logger.debug(f"Failed to format date '{created_at}': {e}")
            return str(created_at)

    def extract_gpt_fields(self, gpt: dict[str, Any], format_for_tui: bool = False) -> GPTTableRow:
        """Extract fields from GPT data for table display.

        Args:
            gpt: GPT data dictionary
            format_for_tui: If True, use TUI-specific formatting
        """
        # Get GPT ID
        gpt_id = str(gpt.get("id", ""))

        # Get latest configuration
        latest_config = self.get_latest_config(gpt)

        # Extract basic information
        name, description, instructions = self.extract_basic_info(latest_config)

        # Extract categories
        categories = self.extract_categories(latest_config)

        # Extract conversation starters
        conversation_starters = self.extract_conversation_starters(latest_config)

        # Extract tools
        tools = self.extract_tools_info(latest_config)

        # Extract files - use numbered list format for TUI
        files_info = self.extract_files_info(latest_config, numbered_list=format_for_tui)

        # Extract owner information
        owner_info = self.extract_owner_info(gpt, format_for_tui=format_for_tui)

        # Extract sharing information
        sharing_visibility, shared_with_info = self.extract_sharing_info(gpt)

        # Format creation date
        created_at = self.format_created_date(gpt.get("created_at", ""))

        return GPTTableRow(
            gpt_id=gpt_id,
            name=name,
            description=description,
            owner_info=owner_info,
            created_at=created_at,
            instructions=instructions,
            categories=categories,
            sharing_visibility=sharing_visibility,
            shared_with_info=shared_with_info,
            conversation_starters=conversation_starters,
            tools=tools,
            files_info=files_info,
        )
