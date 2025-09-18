"""Cache-related data models."""

from typing import Any

from pydantic import BaseModel, Field


class CacheCheckpoint(BaseModel):
    """Model for cache checkpoint data."""

    last_gpt_id: str
    last_page: int
    total_items: int
    timestamp: float


class CachePage(BaseModel):
    """Model for a cached page of data."""

    page: int
    data: list[dict[str, Any]]  # Raw GPT data from API
    last_id: str | None = None
    count: int
    timestamp: float


class CompleteCache(BaseModel):
    """Model for complete cached results."""

    workspace_id: str
    total_items: int
    total_pages: int
    cached_at: float
    data: list[dict[str, Any]]  # Raw GPT data from API


class CacheStatusInfo(BaseModel):
    """Model for cache status information."""

    has_complete_cache: bool = False
    has_incomplete_cache: bool = False
    total_items: int = 0
    cache_age_hours: float | None = None
    last_page: int | None = None
    last_gpt_id: str | None = None


class LoadedCacheResult(BaseModel):
    """Result from loading cached GPT data."""

    data: list[dict[str, Any]] = Field(default_factory=list)
    used_cache: bool = False
