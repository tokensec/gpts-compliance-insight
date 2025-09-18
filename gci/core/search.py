"""Fast fuzzy search and filtering for GPT data."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

import dateparser
from diskcache import Cache
from rapidfuzz import fuzz, process

from gci.models.gpt import GPT

logger = logging.getLogger(__name__)


class GPTSearcher:
    """Fast fuzzy search and filtering for GPT data with caching."""

    def __init__(self, workspace_id: str) -> None:
        """Initialize searcher with workspace-specific cache."""
        self.workspace_id = workspace_id
        cache_dir = Path.home() / ".gci" / "cache" / workspace_id / "search"
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = Cache(str(cache_dir))

    def filter_and_search(
        self,
        gpts_data: list[dict[str, Any]],
        search_query: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        threshold: int = 70,
    ) -> list[dict[str, Any]]:
        """Combined filtering and searching in one pass.

        Args:
            gpts_data: List of GPT dictionaries
            search_query: Optional fuzzy search query
            created_after: Optional date string for filtering
            created_before: Optional date string for filtering
            threshold: Minimum score for fuzzy matches (0-100)

        Returns:
            Filtered list of GPT dictionaries
        """
        # Step 1: Date filtering (if needed)
        if created_after or created_before:
            gpts_data = self._filter_by_date(gpts_data, created_after, created_before)

        # Step 2: Text search (if needed)
        if search_query:
            gpts_data = self._fuzzy_search(gpts_data, search_query, threshold)

        return gpts_data

    def _filter_by_date(
        self,
        gpts_data: list[dict[str, Any]],
        after_str: str | None,
        before_str: str | None,
    ) -> list[dict[str, Any]]:
        """Filter GPTs by creation date."""
        after_dt = dateparser.parse(after_str) if after_str else None
        before_dt = dateparser.parse(before_str) if before_str else None

        if not after_dt and not before_dt:
            return gpts_data

        filtered = []
        for gpt in gpts_data:
            created = gpt.get("created_at", 0)

            # Parse creation date
            gpt_dt = None
            if isinstance(created, int | float):
                gpt_dt = datetime.fromtimestamp(created)
            elif isinstance(created, str):
                gpt_dt = dateparser.parse(created)

            if gpt_dt:
                # Check if within date range
                if after_dt and gpt_dt < after_dt:
                    continue
                if before_dt and gpt_dt > before_dt:
                    continue
                filtered.append(gpt)

        return filtered

    def _fuzzy_search(
        self,
        gpts_data: list[dict[str, Any]],
        query: str,
        threshold: int,
    ) -> list[dict[str, Any]]:
        """Perform fuzzy search with caching."""
        # Get or build search index
        index = self._get_or_build_search_index(gpts_data)

        # Map IDs to GPTs
        id_to_gpt = {gpt["id"]: gpt for gpt in gpts_data}

        # Convert query to lowercase for case-insensitive matching
        query_lower = query.lower()

        # Use partial_ratio for simple phrase matching with typo tolerance
        # This finds the query as a fuzzy substring in the target text
        # Ensures all words must appear together (not scattered)
        matches = process.extract(
            query_lower,
            index,
            scorer=fuzz.partial_ratio,
            score_cutoff=threshold,
            limit=None,  # Return all matches above threshold, not just top N
        )

        # Return matched GPTs sorted by score
        # Note: process.extract with dict returns (value, score, key)
        results = []
        for search_text, score, gpt_id in matches:
            if gpt_id in id_to_gpt:
                gpt = id_to_gpt[gpt_id]
                gpt["_search_score"] = score  # Add score for potential display

                # Find the actual matched substring and its location using alignment
                alignment = fuzz.partial_ratio_alignment(query_lower, search_text)
                if alignment:
                    matched_substring = search_text[alignment.dest_start : alignment.dest_end]
                    gpt["_matched_substring"] = matched_substring

                    # Extract snippet around the match (for display)
                    # Ensure we include the full matched substring in the snippet
                    context_before = 30
                    context_after = 30

                    # Start at least context_before chars before the match, but not before 0
                    start = max(0, alignment.dest_start - context_before)

                    # End at least context_after chars after the match, but not beyond text length
                    end = min(len(search_text), alignment.dest_end + context_after)

                    # Extract the snippet
                    snippet = search_text[start:end]

                    # Adjust the matched substring to be relative to the snippet
                    # This ensures we highlight the right position even with ellipsis
                    match_start_in_snippet = alignment.dest_start - start
                    match_end_in_snippet = alignment.dest_end - start
                    matched_in_snippet = snippet[match_start_in_snippet:match_end_in_snippet]

                    # Add ellipsis if needed
                    if start > 0:
                        snippet = "..." + snippet
                        # Adjust position due to ellipsis
                        matched_in_snippet = snippet[match_start_in_snippet + 3 : match_end_in_snippet + 3]
                    if end < len(search_text):
                        snippet = snippet + "..."

                    gpt["_match_snippet"] = snippet
                    # Store the actual text to highlight (accounting for ellipsis)
                    gpt["_matched_substring"] = matched_in_snippet
                else:
                    # Fallback if alignment fails
                    gpt["_matched_substring"] = query_lower
                    gpt["_match_snippet"] = search_text[:60] + "..."

                results.append(gpt)

        return results

    def _get_or_build_search_index(self, gpts_data: list[dict[str, Any]]) -> dict[str, str]:
        """Build search index using Pydantic model dump."""
        cache_key = f"search_index_{self.workspace_id}"

        # Check cache
        if cache_key in self.cache:
            logger.debug("Using cached search index")
            return self.cache[cache_key]

        # Build new index
        logger.debug("Building new search index")
        index = {}
        for gpt_dict in gpts_data:
            try:
                # Parse into Pydantic model for proper validation and serialization
                gpt = GPT.model_validate(gpt_dict)
                gpt_id = gpt.id

                # Dump entire model to JSON for comprehensive searching
                # This automatically includes ALL fields with proper serialization
                search_text = gpt.model_dump_json().lower()

                # Optional: Add extra weight to name by prepending it twice
                name = ""
                if gpt.latest_config and gpt.latest_config.data:
                    name = gpt.latest_config.data[0].name or ""
                    search_text = f"{name.lower()} {name.lower()} {search_text}"

                index[gpt_id] = search_text
            except Exception as e:
                # Fallback for invalid data that doesn't validate
                logger.debug(f"Failed to parse GPT {gpt_dict.get('id', 'unknown')}: {e}")
                gpt_id = str(gpt_dict.get("id", ""))
                if gpt_id:
                    # Use raw JSON dump as fallback
                    index[gpt_id] = json.dumps(gpt_dict, default=str).lower()

        # Cache the index
        self.cache[cache_key] = index
        return index

    def search_with_highlights(
        self,
        query: str,
        gpts_data: list[dict[str, Any]],
        threshold: int = 70,
    ) -> list[tuple[dict[str, Any], float, list[str]]]:
        """Search with highlight pattern extraction.

        Returns:
            List of tuples: (gpt_dict, score, highlight_patterns)
            - gpt_dict: the matched GPT
            - score: match confidence (0-100)
            - highlight_patterns: list of strings to highlight
        """
        # First, get matches using existing search
        matches = self.filter_and_search(
            gpts_data,
            search_query=query,
            threshold=threshold,
        )

        results = []
        for gpt in matches:
            score = gpt.pop("_search_score", 0)

            # Just use the query itself as the single pattern
            highlight_patterns = [query.strip()] if query.strip() else []

            results.append((gpt, score, highlight_patterns))

        return results

    def clear_cache(self) -> None:
        """Clear the search index cache."""
        self.cache.clear()

    def __del__(self) -> None:
        """Close cache when object is destroyed."""
        if hasattr(self, "cache"):
            self.cache.close()
