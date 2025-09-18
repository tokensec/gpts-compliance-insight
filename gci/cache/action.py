"""Cache management for action analyses using DiskCache TTL."""

import logging
from typing import Any

from gci.cache.base import SimpleCacheManager
from gci.models.action import GPTActionAnalysis

logger = logging.getLogger(__name__)


class ActionAnalysisCache(SimpleCacheManager):
    """Manages local caching of action analysis results."""

    def __init__(self, workspace_id: str) -> None:
        """Initialize cache for action analyses."""
        super().__init__(workspace_id, cache_subdir="actions")

    def _generate_cache_key(
        self,
        gpt_id: str,
        action_domain: str,
        llm_model: str,
        llm_provider: str,
    ) -> str:
        """Generate a cache key based on action data and LLM config.

        Args:
            gpt_id: GPT identifier
            action_domain: Domain of the custom action
            llm_model: LLM model used for analysis
            llm_provider: LLM provider used for analysis

        Returns:
            Unique cache key
        """
        # Create a simple, readable cache key (similar to risk cache)
        domain_key = action_domain if action_domain else "no_domain"
        return f"{gpt_id}_{llm_provider}_{llm_model}_{domain_key}"

    def get_analysis(
        self,
        gpt_id: str,
        action_domain: str,
        llm_model: str,
        llm_provider: str,
    ) -> GPTActionAnalysis | None:
        """Get cached action analysis if it exists.

        Args:
            gpt_id: GPT identifier
            action_domain: Domain of the custom action
            llm_model: LLM model used for analysis
            llm_provider: LLM provider used for analysis

        Returns:
            Cached analysis or None if not found
        """
        cache_key = self._generate_cache_key(gpt_id, action_domain, llm_model, llm_provider)

        try:
            cached_data = self.load(cache_key)
            if cached_data and isinstance(cached_data, dict):
                return GPTActionAnalysis.model_validate(cached_data)
        except Exception as e:
            logger.debug(f"Error loading cached analysis for {cache_key}: {e}")

        return None

    def save_analysis(
        self,
        analysis: GPTActionAnalysis,
        llm_model: str,
        llm_provider: str,
        ttl_hours: float = 24,
    ) -> None:
        """Save action analysis to cache with TTL.

        Args:
            analysis: Action analysis to cache
            llm_model: LLM model used for analysis
            llm_provider: LLM provider used for analysis
            ttl_hours: Time to live in hours (default: 24)
        """
        cache_key = self._generate_cache_key(analysis.gpt_id, analysis.domain, llm_model, llm_provider)

        try:
            # Use DiskCache's built-in TTL feature
            self.save_with_ttl(cache_key, analysis.model_dump(), ttl_hours=ttl_hours)
            logger.debug(f"Cached analysis for action {analysis.action_name} with {ttl_hours}h TTL")

        except Exception as e:
            logger.error(f"Error caching analysis for {cache_key}: {e}")

    def get_batch_analyses(
        self,
        actions_data: list[tuple[str, str, str]],
        llm_model: str,
        llm_provider: str,
    ) -> tuple[list[GPTActionAnalysis], list[tuple[str, str, str]]]:
        """Get cached analyses for a batch.

        Args:
            actions_data: List of (gpt_id, gpt_name, action_domain) tuples
            llm_model: LLM model used for analysis
            llm_provider: LLM provider used for analysis

        Returns:
            Tuple of (cached_analyses, uncached_actions_data)
        """
        cached_analyses = []
        uncached_actions = []

        for gpt_id, gpt_name, action_domain in actions_data:
            cached_analysis = self.get_analysis(gpt_id, action_domain, llm_model, llm_provider)

            if cached_analysis:
                cached_analyses.append(cached_analysis)
            else:
                uncached_actions.append((gpt_id, gpt_name, action_domain))

        return cached_analyses, uncached_actions

    def save_batch_analyses(
        self,
        analyses: list[GPTActionAnalysis],
        llm_model: str,
        llm_provider: str,
        ttl_hours: float = 24,
    ) -> None:
        """Save a batch of analyses to cache.

        Args:
            analyses: List of action analyses
            llm_model: LLM model used for analysis
            llm_provider: LLM provider used for analysis
            ttl_hours: Time to live in hours
        """
        for analysis in analyses:
            self.save_analysis(analysis, llm_model, llm_provider, ttl_hours)

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
