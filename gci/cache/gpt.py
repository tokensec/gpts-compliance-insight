"""Sync cache management for GPT data using DiskCache."""

import logging
import time
from pathlib import Path
from typing import Any

from diskcache import Cache

from gci.models.cache import CacheCheckpoint, CachePage, CompleteCache

logger = logging.getLogger(__name__)


class GPTCache:
    """Manages local caching of GPT data pages using DiskCache."""

    def __init__(self, workspace_id: str) -> None:
        """Initialize cache for a specific workspace."""
        self.workspace_id = workspace_id
        cache_dir = Path.home() / ".gci" / "cache" / workspace_id
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = Cache(str(cache_dir))

    def save_page(self, page_num: int, data: list[dict[str, Any]], last_id: str | None = None) -> None:
        """Save a page of GPT data to cache."""
        cache_page = CachePage(page=page_num, data=data, last_id=last_id, count=len(data), timestamp=time.time())
        self.cache.set(f"page_{page_num}", cache_page.model_dump())

    def save_checkpoint(self, last_gpt_id: str, page_num: int, total_items: int) -> None:
        """Save checkpoint information."""
        checkpoint = CacheCheckpoint(
            last_gpt_id=last_gpt_id, last_page=page_num, total_items=total_items, timestamp=time.time()
        )
        self.cache.set("checkpoint", checkpoint.model_dump())

    def load_checkpoint(self) -> CacheCheckpoint | None:
        """Load checkpoint information if it exists."""
        try:
            checkpoint_data = self.cache.get("checkpoint")
            if checkpoint_data:
                return CacheCheckpoint.model_validate(checkpoint_data)
        except Exception as e:
            logger.debug(f"Checkpoint could not be loaded (expected if no cache exists): {e}")
        return None

    def load_cached_pages(self, up_to_page: int | None = None) -> list[dict[str, Any]]:
        """Load all cached pages up to specified page number."""
        results = []
        page_num = 1

        while True:
            if up_to_page and page_num > up_to_page:
                break

            try:
                page_data = self.cache.get(f"page_{page_num}")
                if not page_data:
                    break

                cache_page = CachePage.model_validate(page_data)
                results.extend(cache_page.data)
            except Exception as e:
                logger.debug(f"Cache page {page_num} could not be loaded, stopping cache loading: {e}")
                break

            page_num += 1

        return results

    def remove_checkpoint(self) -> None:
        """Remove checkpoint file after successful completion."""
        try:
            self.cache.delete("checkpoint")
        except Exception as e:
            logger.debug(f"Could not remove checkpoint (may not exist): {e}")

    def clear_cache(self) -> None:
        """Clear all cached data for this workspace."""
        self.cache.clear()

    def has_cache(self) -> bool:
        """Check if any cache exists."""
        if "checkpoint" in self.cache:
            return True

        if "complete" in self.cache:
            return True

        return "page_1" in self.cache

    def save_complete_results(self, results: list[dict[str, Any]], total_pages: int) -> None:
        """Save complete results after successful pagination."""
        complete_cache = CompleteCache(
            workspace_id=self.workspace_id,
            total_items=len(results),
            total_pages=total_pages,
            cached_at=time.time(),
            data=results,
        )
        self.cache.set("complete", complete_cache.model_dump())

    def load_complete_results(self) -> CompleteCache | None:
        """Load complete cached results if available and recent."""
        try:
            complete_data = self.cache.get("complete")
            if complete_data:
                return CompleteCache.model_validate(complete_data)
        except Exception as e:
            logger.debug(f"Complete cache could not be loaded: {e}")
        return None

    def has_complete_cache(self) -> bool:
        """Check if complete cache exists."""
        return "complete" in self.cache

    def __del__(self) -> None:
        """Close cache when object is destroyed."""
        if hasattr(self, "cache"):
            self.cache.close()
