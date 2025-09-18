"""GPT-related data models for Compliance API."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class Permissions(BaseModel):
    """Permissions model for GPT sharing."""

    object: Literal["compliance.workspace.gpt.permissions"] = "compliance.workspace.gpt.permissions"
    can_read: bool = True
    can_view_config: bool = False
    can_write: bool = False


class SharedUser(BaseModel):
    """Model for users with whom a GPT is shared."""

    object: Literal["compliance.workspace.gpt.shared_user"] = "compliance.workspace.gpt.shared_user"
    id: str  # user-XXXXXXXXXXXXXXXXXXXXXXXX format
    email: str | None = None
    permissions: Permissions | None = None


class Recipients(BaseModel):
    """Recipients list for GPT sharing."""

    object: Literal["list"] = "list"
    data: list[SharedUser] = Field(default_factory=list)
    last_id: str | None = None
    has_more: bool = False


class Sharing(BaseModel):
    """Sharing configuration for a GPT."""

    object: Literal["compliance.workspace.gpt.sharing"] = "compliance.workspace.gpt.sharing"
    visibility: Literal["invite-only", "workspace-with-link", "workspace", "anyone-with-link", "gpt-store"] = (
        "invite-only"
    )
    permissions: Permissions | None = None
    recipients: Recipients | None = None


class GPTFile(BaseModel):
    """Model for files attached to a GPT."""

    object: Literal["compliance.workspace.gpt.file"] | None = "compliance.workspace.gpt.file"
    id: str  # file-XXXXXXXXXXXXXXXXXXXXXXXX format
    name: str | None = None
    created_at: float | None = None  # Unix timestamp
    download_url: HttpUrl | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> float | None:
        """Parse timestamp from various formats."""
        if v is None:
            return None
        if isinstance(v, int | float):
            return float(v)
        if isinstance(v, datetime):
            return v.timestamp()
        if isinstance(v, str):
            try:
                return datetime.fromisoformat(v).timestamp()
            except (ValueError, TypeError):
                return None
        return None

    @property
    def created_datetime(self) -> datetime | None:
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(self.created_at) if self.created_at else None


class GPTFileInfo(BaseModel):
    """Simplified file info model (used when file_format=id)."""

    object: Literal["compliance.workspace.gpt.file_info"] = "compliance.workspace.gpt.file_info"
    id: str
    name: str | None = None


class GPTFileList(BaseModel):
    """List of GPT files."""

    object: Literal["list"] = "list"
    data: list[GPTFile | GPTFileInfo] = Field(default_factory=list)
    last_id: str | None = None
    has_more: bool = False


class GPTTool(BaseModel):
    """Model for tools available to a GPT."""

    type: str  # Allow any tool type from API
    created_at: float | None = None  # Unix timestamp
    # Custom action specific fields
    action_domain: str | None = None
    action_openapi_raw: str | None = None
    action_privacy_policy_url: str | None = None
    auth_type: str | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> float | None:
        """Parse timestamp from various formats."""
        if v is None:
            return None
        if isinstance(v, int | float):
            return float(v)
        if isinstance(v, datetime):
            return v.timestamp()
        return None

    @property
    def created_datetime(self) -> datetime | None:
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(self.created_at) if self.created_at else None

    @property
    def is_custom_action(self) -> bool:
        """Check if this is a custom action tool."""
        return self.type in ("custom-action", "custom_action", "action")


class GPTToolList(BaseModel):
    """List of GPT tools."""

    object: Literal["list"] = "list"
    data: list[GPTTool] = Field(default_factory=list)
    last_id: str | None = None
    has_more: bool = False


class GPTVersionAuthor(BaseModel):
    """Version author information for a GPT config."""

    object: Literal["compliance.workspace.gpt.version_author"] | None = "compliance.workspace.gpt.version_author"
    id: str  # user ID
    email: str | None = None


class GPTConfig(BaseModel):
    """Model for GPT configuration."""

    object: Literal["compliance.workspace.gpt.configuration"] | None = "compliance.workspace.gpt.configuration"
    id: str  # gzm_cnf_xxxxxxxxxxxxxxxxxxxxxxxx format
    name: str | None = None
    description: str | None = None
    categories: list[str] = Field(default_factory=list)
    conversation_starters: list[str] = Field(default_factory=list)
    created_at: float | None = None  # Unix timestamp
    instructions: str | None = None
    version_author: GPTVersionAuthor | None = None
    files: GPTFileList | None = None
    tools: GPTToolList | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> float | None:
        """Parse timestamp from various formats."""
        if v is None:
            return None
        if isinstance(v, int | float):
            return float(v)
        if isinstance(v, datetime):
            return v.timestamp()
        return None

    @property
    def created_datetime(self) -> datetime | None:
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(self.created_at) if self.created_at else None


class GPTConfigList(BaseModel):
    """List of GPT configurations."""

    object: Literal["list"] = "list"
    data: list[GPTConfig] = Field(default_factory=list)
    last_id: str | None = None
    has_more: bool = False


class GPT(BaseModel):
    """Complete GPT model matching API response."""

    object: Literal["compliance.workspace.gpt"] | None = "compliance.workspace.gpt"
    id: str  # g-XXXXXXXXX format
    created_at: float | None = None  # Unix timestamp
    owner_id: str | None = None  # user-XXXXXXXXXXXXXXXXXXXXXXXX format
    owner_email: str | None = None
    builder_name: str | None = None
    sharing: Sharing | None = None
    latest_config: GPTConfigList | None = None

    @field_validator("created_at", mode="before")
    @classmethod
    def parse_timestamp(cls, v: Any) -> float | None:
        """Parse timestamp from various formats."""
        if v is None:
            return None
        if isinstance(v, int | float):
            return float(v)
        if isinstance(v, datetime):
            return v.timestamp()
        return None

    @property
    def created_datetime(self) -> datetime | None:
        """Convert Unix timestamp to datetime."""
        return datetime.fromtimestamp(self.created_at) if self.created_at else None

    @property
    def name(self) -> str | None:
        """Get GPT name from latest config."""
        if self.latest_config and self.latest_config.data:
            return self.latest_config.data[0].name
        return None

    @property
    def description(self) -> str | None:
        """Get GPT description from latest config."""
        if self.latest_config and self.latest_config.data:
            return self.latest_config.data[0].description
        return None

    @property
    def instructions(self) -> str | None:
        """Get GPT instructions from latest config."""
        if self.latest_config and self.latest_config.data:
            return self.latest_config.data[0].instructions
        return None

    @property
    def files(self) -> list[GPTFile]:
        """Get files from latest config."""
        if self.latest_config and self.latest_config.data:
            config = self.latest_config.data[0]
            if config.files and config.files.data:
                return [f for f in config.files.data if isinstance(f, GPTFile)]
        return []

    @property
    def tools(self) -> list[GPTTool]:
        """Get tools from latest config."""
        if self.latest_config and self.latest_config.data:
            config = self.latest_config.data[0]
            if config.tools and config.tools.data:
                return config.tools.data
        return []

    @property
    def has_custom_actions(self) -> bool:
        """Check if GPT has custom actions."""
        return any(tool.is_custom_action for tool in self.tools)

    @property
    def shared_users_count(self) -> int:
        """Get count of shared users."""
        if self.sharing and self.sharing.recipients:
            return len(self.sharing.recipients.data)
        return 0

    @property
    def sharing_visibility(self) -> str | None:
        """Get sharing visibility."""
        return self.sharing.visibility if self.sharing else None
