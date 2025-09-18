"""Download GPTs command implementation."""

import logging
import time
from typing import Annotated

import typer
from rich.console import Console

from gci.cache import GPTCache
from gci.cli.utils.auth import get_api_credentials, with_api_client
from gci.models.stats import DownloadResult

console = Console()
logger = logging.getLogger(__name__)


def download_gpts(
    workspace_id: Annotated[
        str | None,
        typer.Option(
            "--workspace-id",
            "-w",
            help="OpenAI workspace ID (auto-detected from GCI_OPENAI_WORKSPACE_ID env var)",
        ),
    ] = None,
    api_key: Annotated[
        str | None,
        typer.Option(
            "--api-key",
            "-k",
            help="OpenAI API key (auto-detected from GCI_OPENAI_API_KEY env var)",
            hide_input=True,
        ),
    ] = None,
    force: Annotated[
        bool,
        typer.Option(
            "--force",
            "-f",
            help="Force fresh download, clearing any cached data",
        ),
    ] = False,
) -> None:
    """Download all GPTs from the workspace and cache them locally.

    This command fetches GPT data from the OpenAI Compliance API and caches it.
    If an incomplete download is detected, you'll be prompted to continue or start fresh.
    Use --force to clear cache and download everything from scratch.
    """
    api_key, workspace_id = get_api_credentials(api_key, workspace_id)

    def _download_gpts() -> DownloadResult:
        """Internal function to download GPTs."""
        cache = GPTCache(workspace_id)
        resume_from = None

        # Handle force download
        if force:
            console.print("[yellow]Clearing cache and starting fresh download...[/yellow]")
            cache.clear_cache()
        else:
            # Check for complete cache
            if cache.has_complete_cache():
                complete_data = cache.load_complete_results()
                if complete_data:
                    cached_time = time.time() - complete_data.cached_at
                    hours_old = cached_time / 3600
                    console.print(
                        f"[green]✓ Complete cache available[/green] | "
                        f"{complete_data.total_items} GPTs | {hours_old:.1f} hours old"
                    )
                    return DownloadResult(gpts_data=complete_data.data)

            # Check for incomplete session
            elif cache.has_cache():
                checkpoint = cache.load_checkpoint()
                if checkpoint:
                    console.print(
                        f"[yellow]⚠ Incomplete download found[/yellow] | "
                        f"Page {checkpoint.last_page} | {checkpoint.total_items} items downloaded"
                    )

                    if typer.confirm("Continue from where you left off?", default=True):
                        resume_from = checkpoint.last_gpt_id
                        console.print("[green]✓ Resuming download[/green]")
                    else:
                        console.print("[yellow]Starting fresh download...[/yellow]")
                        cache.clear_cache()

        # Connect to API and download
        client = with_api_client(api_key, workspace_id)
        with client:
            console.print("[bold blue]Downloading GPTs...[/bold blue]")

            # Call the internal paginate method directly to get raw data
            endpoint = f"/compliance/workspaces/{client.workspace_id}/gpts"
            gpts_data = client._paginate(  # type: ignore[attr-defined]
                endpoint, params={"limit": 100}, cache_key=client.workspace_id, resume_from=resume_from
            )

            console.print(f"[green]✓ Downloaded {len(gpts_data)} GPTs[/green]")
            return DownloadResult(gpts_data=gpts_data)

    # Run the download
    result = _download_gpts()

    if result.gpts_data:
        console.print("[green]✓ GPT data ready for use with 'gci list' command[/green]")
    else:
        console.print(f"[yellow]No GPTs found in workspace {workspace_id}[/yellow]")
