"""Shared data access utilities for CLI commands."""

import time

import typer
from rich.console import Console

from gci.cache import GPTCache
from gci.models.cache import CacheStatusInfo, LoadedCacheResult

console = Console()


def load_cached_gpts(
    workspace_id: str,
    force_fresh: bool = False,
    auto_accept: bool = False,
) -> LoadedCacheResult:
    """Load GPT data from cache if available.

    Args:
        workspace_id: The workspace ID to load data for
        force_fresh: If True, ignore cache and return empty list
        auto_accept: If True, automatically use cached data without prompting

    Returns:
        LoadedCacheResult with data and used_cache flag
    """
    if force_fresh:
        return LoadedCacheResult(data=[], used_cache=False)

    cache = GPTCache(workspace_id)

    # Check for complete cache first
    if cache.has_complete_cache():
        complete_data = cache.load_complete_results()
        if complete_data:
            cached_time = time.time() - complete_data.cached_at
            hours_old = cached_time / 3600

            console.print(
                f"\n[yellow]Found cached results ({complete_data.total_items} GPTs, {hours_old:.1f} hours old)[/yellow]"
            )

            if auto_accept or typer.confirm("Use cached results?", default=True):
                console.print("[green]✓ Using cached results[/green]")
                return LoadedCacheResult(data=complete_data.data, used_cache=True)
            else:
                console.print("[yellow]Cached data declined, will fetch fresh data[/yellow]")
                return LoadedCacheResult(data=[], used_cache=False)

    # Check for incomplete cache (checkpoint exists)
    if cache.has_cache():
        checkpoint = cache.load_checkpoint()
        if checkpoint:
            console.print("\n[yellow]Found incomplete download session:[/yellow]")
            console.print(f"  Last GPT ID: {checkpoint.last_gpt_id}")
            console.print(f"  Last page: {checkpoint.last_page}")
            console.print(f"  Items collected: {checkpoint.total_items}")
            console.print("\n[dim]Note: Use 'gci download --resume' to continue this session[/dim]")

    return LoadedCacheResult(data=[], used_cache=False)


def get_cache_status(workspace_id: str) -> CacheStatusInfo:
    """Get the status of cached data for a workspace.

    Args:
        workspace_id: The workspace ID to check

    Returns:
        CacheStatusInfo with cache status information
    """
    cache = GPTCache(workspace_id)
    status = CacheStatusInfo()

    # Check complete cache
    if cache.has_complete_cache():
        complete_data = cache.load_complete_results()
        if complete_data:
            status.has_complete_cache = True
            status.total_items = complete_data.total_items
            cached_time = time.time() - complete_data.cached_at
            status.cache_age_hours = cached_time / 3600

    # Check incomplete cache
    if cache.has_cache():
        checkpoint = cache.load_checkpoint()
        if checkpoint:
            status.has_incomplete_cache = True
            status.last_page = checkpoint.last_page
            status.last_gpt_id = checkpoint.last_gpt_id
            if not status.has_complete_cache:
                status.total_items = checkpoint.total_items

    return status
