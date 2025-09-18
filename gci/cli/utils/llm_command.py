"""Shared utilities for LLM-based CLI commands."""

import logging
from typing import Any, Protocol

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn

from gci.cli.utils.auth import get_api_credentials
from gci.cli.utils.data import load_cached_gpts
from gci.llm.client import LLMClient
from gci.models.gpt import GPT

console = Console()
logger = logging.getLogger(__name__)


class BatchProcessor(Protocol):
    """Protocol for batch processing services."""

    def process_batch(self, batch_data: Any) -> Any:
        """Process a batch of data."""
        ...


def initialize_llm_client(
    llm_provider: str | None = None,
    llm_model: str | None = None,
    llm_api_key: str | None = None,
    llm_temperature: float | None = None,
) -> LLMClient:
    """Initialize and validate LLM client.

    Args:
        llm_provider: LLM provider name
        llm_model: LLM model name
        llm_api_key: API key for LLM
        llm_temperature: Temperature setting

    Returns:
        Initialized LLM client

    Raises:
        typer.Exit: If initialization or validation fails
    """
    try:
        llm_client = LLMClient(
            provider=llm_provider,
            model=llm_model,
            api_key=llm_api_key,
            temperature=llm_temperature,
        )
        console.print(f"[dim]Using LLM: {llm_client}[/dim]")
    except Exception as e:
        console.print(f"[red]Error initializing LLM client: {e}[/red]")
        console.print("[dim]Check your LLM configuration and API keys.[/dim]")
        raise typer.Exit(1) from e

    # Validate LLM connection
    console.print("[dim]Validating LLM connection...[/dim]")
    try:
        llm_client.validate()
        console.print("[green]✓ LLM connection validated[/green]")
    except Exception as e:
        console.print(f"[red]Error: LLM validation failed: {e}[/red]")
        if llm_provider == "bedrock":
            console.print("[dim]For AWS Bedrock, ensure AWS_PROFILE is set[/dim]")
        raise typer.Exit(1) from e

    return llm_client


def load_and_validate_gpts(
    workspace_id: str | None,
    no_download: bool = False,
    search_query: str | None = None,
) -> tuple[list[GPT], str]:
    """Load GPT data from cache and validate.

    Args:
        workspace_id: Workspace ID
        no_download: Whether to skip download prompt
        search_query: Optional search query to filter GPTs

    Returns:
        Tuple of (GPT list, workspace_id)

    Raises:
        typer.Exit: If no data found or loading fails
    """
    # Get workspace credentials
    _, workspace_id = get_api_credentials(None, workspace_id)

    # Load GPT data
    cache_result = load_cached_gpts(
        workspace_id,
        force_fresh=False,
        auto_accept=True,
    )

    if not cache_result.data:
        if no_download:
            console.print("[yellow]No cached data found.[/yellow]")
            console.print("[dim]Use 'gci download' to fetch GPT data first.[/dim]")
        else:
            console.print("[yellow]No cached data found. Please run 'gci download' first.[/yellow]")
        raise typer.Exit(1)

    # Convert raw dicts to GPT models
    gpts_data: list[GPT] = []
    for gpt_dict in cache_result.data:
        try:
            gpt_model = GPT.model_validate(gpt_dict)
            gpts_data.append(gpt_model)
        except Exception as e:
            logger.warning(f"Failed to parse GPT: {e}")
            continue

    console.print(f"[dim]Loaded {len(gpts_data)} GPTs from cache[/dim]")

    # Apply search filter if provided
    if search_query:
        from gci.core.search import GPTSearcher

        searcher = GPTSearcher(workspace_id)
        gpts_as_dicts = [gpt.model_dump() for gpt in gpts_data]
        filtered_dicts = searcher.filter_and_search(gpts_as_dicts, search_query=search_query)
        gpts_data = [GPT.model_validate(d) for d in filtered_dicts]
        console.print(f"[dim]Filtered to {len(gpts_data)} GPTs matching '{search_query}'[/dim]")

    return gpts_data, workspace_id


def create_progress_bar() -> Progress:
    """Create a consistent progress bar for batch processing.

    Returns:
        Configured Progress instance
    """
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
    )


def process_in_batches(
    items: list[Any],
    batch_size: int,
    processor: Any,  # Callable that processes batches
    progress_description: str = "Processing",
    on_error: Any = None,  # Optional error handler callable
) -> list[Any]:
    """Process items in batches with progress tracking.

    Args:
        items: Items to process
        batch_size: Size of each batch
        processor: Function to process each batch
        progress_description: Description for progress bar
        on_error: Optional error handler

    Returns:
        List of all processed results
    """
    if not items:
        return []

    total_batches = (len(items) + batch_size - 1) // batch_size
    all_results = []

    with create_progress_bar() as progress:
        task = progress.add_task(f"{progress_description}...", total=len(items))

        for i in range(0, len(items), batch_size):
            batch_data = items[i : i + batch_size]
            batch_num = (i // batch_size) + 1

            progress.update(task, description=f"{progress_description} batch {batch_num}/{total_batches}...")

            try:
                batch_results = processor(batch_data)
                all_results.extend(batch_results if isinstance(batch_results, list) else [batch_results])
                progress.update(task, advance=len(batch_data))

            except Exception as e:
                logger.error(f"Error processing batch {batch_num}: {e}")
                if on_error:
                    error_results = on_error(batch_data, e)
                    all_results.extend(error_results if isinstance(error_results, list) else [error_results])
                progress.update(task, advance=len(batch_data))

    return all_results
