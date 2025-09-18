"""Base cache class for all cache implementations."""

import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Generic, TypeVar

from diskcache import Cache

logger = logging.getLogger(__name__)

T = TypeVar("T")


class BaseCacheManager(ABC, Generic[T]):
    """Abstract base class for cache managers."""

    def __init__(self, workspace_id: str, cache_subdir: str | None = None) -> None:
        """Initialize cache manager.

        Args:
            workspace_id: Workspace identifier for cache isolation
            cache_subdir: Optional subdirectory within workspace cache
        """
        self.workspace_id = workspace_id

        # Create cache directory
        cache_path = Path.home() / ".gci" / "cache" / workspace_id
        if cache_subdir:
            cache_path = cache_path / cache_subdir

        cache_path.mkdir(parents=True, exist_ok=True)

        # Initialize DiskCache
        self.cache = Cache(str(cache_path))
        self.cache_path = cache_path

        logger.debug(f"Initialized cache at {cache_path}")

    def clear_cache(self) -> None:
        """Clear all cached data."""
        try:
            self.cache.clear()
            logger.info(f"Cleared cache for workspace {self.workspace_id}")
        except Exception as e:
            logger.error(f"Error clearing cache: {e}")

    def has_cache(self) -> bool:
        """Check if any cache exists.

        Returns:
            True if cache has any entries
        """
        return len(self.cache) > 0

    def get_cache_size(self) -> int:
        """Get number of items in cache.

        Returns:
            Number of cached items
        """
        return len(self.cache)

    def delete_item(self, key: str) -> bool:
        """Delete a specific cache item.

        Args:
            key: Cache key to delete

        Returns:
            True if item was deleted, False if not found
        """
        try:
            if key in self.cache:
                del self.cache[key]
                return True
            return False
        except Exception as e:
            logger.error(f"Error deleting cache item {key}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if a cache key exists.

        Args:
            key: Cache key to check

        Returns:
            True if key exists in cache
        """
        return key in self.cache

    @abstractmethod
    def save(self, key: str, data: T) -> None:
        """Save data to cache.

        Args:
            key: Cache key
            data: Data to cache
        """
        pass

    @abstractmethod
    def load(self, key: str) -> T | None:
        """Load data from cache.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found
        """
        pass


class SimpleCacheManager(BaseCacheManager[Any]):
    """Simple cache manager for basic key-value storage."""

    def save(self, key: str, data: Any, expire: float | None = None) -> None:
        """Save data to cache with optional expiration.

        Args:
            key: Cache key
            data: Data to cache
            expire: Optional expiration time in seconds
        """
        try:
            self.cache.set(key, data, expire=expire)
            logger.debug(f"Cached data with key: {key}")
        except Exception as e:
            logger.error(f"Error caching data with key {key}: {e}")

    def load(self, key: str) -> Any | None:
        """Load data from cache.

        Args:
            key: Cache key

        Returns:
            Cached data or None if not found
        """
        try:
            return self.cache.get(key)
        except Exception as e:
            logger.debug(f"Error loading cache key {key}: {e}")
            return None

    def save_with_ttl(self, key: str, data: Any, ttl_hours: float = 24) -> None:
        """Save data with TTL in hours.

        Args:
            key: Cache key
            data: Data to cache
            ttl_hours: Time to live in hours
        """
        expire_seconds = ttl_hours * 3600
        self.save(key, data, expire=expire_seconds)
