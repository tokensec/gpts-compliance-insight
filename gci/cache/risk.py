"""Cache management for risk classifications using DiskCache TTL."""

import logging
from typing import Any

from gci.cache.base import SimpleCacheManager
from gci.models.risk import GPTRiskClassification

logger = logging.getLogger(__name__)


class RiskClassificationCache(SimpleCacheManager):
    """Manages local caching of risk classification results."""

    def __init__(self, workspace_id: str) -> None:
        """Initialize cache for risk classifications."""
        super().__init__(workspace_id, cache_subdir="risk")

    def _generate_cache_key(
        self,
        gpt_id: str,
        file_names: list[str],
        llm_model: str,
        llm_provider: str,
    ) -> str:
        """Generate a cache key based on GPT data and LLM config.

        Args:
            gpt_id: GPT identifier
            file_names: List of file names
            llm_model: LLM model used for classification
            llm_provider: LLM provider used for classification

        Returns:
            Unique cache key
        """
        # Create a simple, readable cache key
        files_key = "_".join(sorted(file_names)[:3]) if file_names else "no_files"
        return f"{gpt_id}_{llm_provider}_{llm_model}_{files_key}"

    def get_classification(
        self,
        gpt_id: str,
        file_names: list[str],
        llm_model: str,
        llm_provider: str,
    ) -> GPTRiskClassification | None:
        """Get cached risk classification if it exists.

        Args:
            gpt_id: GPT identifier
            file_names: List of file names
            llm_model: LLM model used for classification
            llm_provider: LLM provider used for classification

        Returns:
            Cached classification or None if not found
        """
        cache_key = self._generate_cache_key(gpt_id, file_names, llm_model, llm_provider)

        try:
            cached_data = self.load(cache_key)
            if cached_data and isinstance(cached_data, dict):
                return GPTRiskClassification.model_validate(cached_data)
        except Exception as e:
            logger.debug(f"Error loading cached classification for {cache_key}: {e}")

        return None

    def save_classification(
        self,
        classification: GPTRiskClassification,
        file_names: list[str],
        llm_model: str,
        llm_provider: str,
        ttl_hours: float = 24,
    ) -> None:
        """Save risk classification to cache with TTL.

        Args:
            classification: Risk classification to cache
            file_names: List of file names used for classification
            llm_model: LLM model used for classification
            llm_provider: LLM provider used for classification
            ttl_hours: Time to live in hours (default: 24)
        """
        cache_key = self._generate_cache_key(classification.gpt_id, file_names, llm_model, llm_provider)

        try:
            # Use DiskCache's built-in TTL feature
            self.save_with_ttl(cache_key, classification.model_dump(), ttl_hours=ttl_hours)
            logger.debug(f"Cached classification for GPT {classification.gpt_name} with {ttl_hours}h TTL")

        except Exception as e:
            logger.error(f"Error caching classification for {cache_key}: {e}")

    def get_batch_classifications(
        self,
        gpts_data: list[tuple[str, str, list[str]]],
        llm_model: str,
        llm_provider: str,
    ) -> tuple[list[GPTRiskClassification], list[tuple[str, str, list[str]]]]:
        """Get cached classifications for a batch.

        Args:
            gpts_data: List of (gpt_id, gpt_name, file_names) tuples
            llm_model: LLM model used for classification
            llm_provider: LLM provider used for classification

        Returns:
            Tuple of (cached_classifications, uncached_gpts_data)
        """
        cached_classifications = []
        uncached_gpts = []

        for gpt_id, gpt_name, file_names in gpts_data:
            cached_classification = self.get_classification(gpt_id, file_names, llm_model, llm_provider)

            if cached_classification:
                cached_classifications.append(cached_classification)
            else:
                uncached_gpts.append((gpt_id, gpt_name, file_names))

        return cached_classifications, uncached_gpts

    def save_batch_classifications(
        self,
        classifications: list[GPTRiskClassification],
        gpts_data: list[tuple[str, str, list[str]]],
        llm_model: str,
        llm_provider: str,
        ttl_hours: float = 24,
    ) -> None:
        """Save a batch of classifications to cache.

        Args:
            classifications: List of risk classifications
            gpts_data: Original GPT data used for classification
            llm_model: LLM model used for classification
            llm_provider: LLM provider used for classification
            ttl_hours: Time to live in hours
        """
        # Create a mapping from gpt_id to file_names for caching
        gpt_files_map = {gpt_id: file_names for gpt_id, _, file_names in gpts_data}

        for classification in classifications:
            file_names = gpt_files_map.get(classification.gpt_id, [])
            self.save_classification(classification, file_names, llm_model, llm_provider, ttl_hours)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        return {
            "total_entries": self.get_cache_size(),
            "workspace_id": self.workspace_id,
            "cache_path": str(self.cache_path),
        }
