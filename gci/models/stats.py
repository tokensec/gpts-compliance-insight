"""Statistics and status tracking models."""

from typing import Any

from pydantic import BaseModel, Field


class DownloadStats(BaseModel):
    """Model for tracking download statistics."""

    start_time: float
    gpts_found: int = 0
    from_cache: bool = False


class DownloadResult(BaseModel):
    """Result from download operation."""

    gpts_data: list[dict[str, Any]] = Field(default_factory=list)
    cache_cleared: bool = False
    total_items: int | None = None
    last_page: int | None = None
    last_gpt_id: str | None = None


class ListCommandStats(BaseModel):
    """Statistics for list command execution."""

    start_time: float
    gpts_found: int = 0
    from_cache: bool = False
    filtered_count: int | None = None
    search_pattern: str | None = None
