"""Risk classifier command implementation."""

import logging
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from gci.cache.risk import RiskClassificationCache
from gci.cli.utils.auth import get_api_credentials
from gci.cli.utils.data import load_cached_gpts
from gci.cli.utils.options import (
    NO_DOWNLOAD_OPTION,
    OUTPUT_PATH_OPTION,
    SEARCH_OPTION,
    WORKSPACE_ID_OPTION,
)
from gci.cli.utils.output import handle_csv_output, handle_json_output
from gci.llm.client import LLMClient
from gci.models.risk import GPTRiskClassification, RiskClassificationBatch, RiskLevel
from gci.services.risk_classifier import RiskClassificationService


class RiskOutputFormat(StrEnum):
    """Output formats for risk classifier."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


console = Console()
logger = logging.getLogger(__name__)


def handle_table_output(batch: RiskClassificationBatch, search_query: str | None = None) -> None:  # noqa: ARG001
    """Handle table format output."""
    table = Table(title="GPT Risk Classifications", show_lines=True)

    table.add_column("Risk", style="bold", width=6, justify="center")
    table.add_column("GPT Name", style="cyan", min_width=20)
    table.add_column("Files", style="dim", min_width=15)
    table.add_column("Reasoning", min_width=30)

    # Sort by risk level (High -> Medium -> Low)
    risk_order = {RiskLevel.HIGH: 0, RiskLevel.MEDIUM: 1, RiskLevel.LOW: 2}
    sorted_classifications = sorted(batch.classifications, key=lambda x: (risk_order[x.risk_level], x.gpt_name.lower()))

    for classification in sorted_classifications:
        risk_display = f"{classification.risk_emoji} {classification.risk_level.value}"

        table.add_row(
            risk_display,
            classification.gpt_name,
            classification.file_names_str,
            classification.reasoning,
        )

    console.print(table)

    # Print summary
    summary = batch.risk_summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"🔴 High Risk: {summary['high']}")
    console.print(f"🟡 Medium Risk: {summary['medium']}")
    console.print(f"🟢 Low Risk: {summary['low']}")
    console.print(f"📊 Total: {summary['total']}")


def transform_batch_for_json(batch: RiskClassificationBatch) -> dict[str, Any]:
    """Transform risk classification batch for JSON output."""
    return {
        "summary": batch.risk_summary,
        "processed_at": batch.processed_at.isoformat(),
        "classifications": [
            {
                "gpt_id": c.gpt_id,
                "gpt_name": c.gpt_name,
                "file_names": c.file_names,
                "risk_level": c.risk_level.value,
                "reasoning": c.reasoning,
                "classified_at": c.classified_at.isoformat(),
            }
            for c in batch.classifications
        ],
    }


def transform_classification_for_csv(classification: GPTRiskClassification) -> dict[str, Any]:
    """Transform a single classification for CSV output."""
    return {
        "gpt_id": classification.gpt_id,
        "gpt_name": classification.gpt_name,
        "file_names": classification.file_names_str,
        "risk_level": classification.risk_level.value,
        "reasoning": classification.reasoning,
        "classified_at": classification.classified_at.isoformat(),
    }


def risk_classifier(
    workspace_id: WORKSPACE_ID_OPTION = None,
    output_format: Annotated[
        RiskOutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format",
            case_sensitive=False,
        ),
    ] = RiskOutputFormat.TABLE,
    output: OUTPUT_PATH_OPTION = None,
    search: SEARCH_OPTION = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-l",
            help="Limit number of GPTs to classify (useful for testing)",
            min=1,
        ),
    ] = None,
    llm_provider: Annotated[
        str | None,
        typer.Option(
            "--llm-provider",
            help="LLM provider (openai, anthropic, claude, etc.)",
        ),
    ] = None,
    llm_model: Annotated[
        str | None,
        typer.Option(
            "--llm-model",
            help="LLM model name (gpt-4, claude-3-sonnet, etc.)",
        ),
    ] = None,
    llm_api_key: Annotated[
        str | None,
        typer.Option(
            "--llm-api-key",
            help="LLM API key (or set via environment)",
            hide_input=True,
        ),
    ] = None,
    llm_temperature: Annotated[
        float | None,
        typer.Option(
            "--llm-temperature",
            help="LLM temperature (0.0-2.0)",
            min=0.0,
            max=2.0,
        ),
    ] = None,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            help="Number of GPTs to process per LLM call",
            min=1,
            max=20,
        ),
    ] = 5,
    no_download: NO_DOWNLOAD_OPTION = False,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Skip cached risk classifications and reclassify all GPTs",
        ),
    ] = False,
) -> None:
    """Classify GPT risk levels based on associated file names.

    This command analyzes GPT configurations and classifies them into High, Medium,
    or Low risk categories based on the file names associated with each GPT.

    Uses LiteLLM for multi-provider LLM support (OpenAI, Anthropic, etc.).
    """
    start_time = datetime.now()

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
            raise typer.Exit(1)
        else:
            console.print("[yellow]No cached data found. Please run 'gci download' first.[/yellow]")
            raise typer.Exit(1)

    # Convert raw dicts to GPT models
    from gci.models.gpt import GPT

    gpts_raw = cache_result.data
    gpts_data: list[GPT] = []

    for gpt_dict in gpts_raw:
        try:
            gpt_model = GPT.model_validate(gpt_dict)
            gpts_data.append(gpt_model)
        except Exception as e:
            logger.warning(f"Failed to parse GPT: {e}")
            # Skip malformed GPTs
            continue

    console.print(f"[dim]Loaded {len(gpts_data)} GPTs from cache[/dim]")

    # Apply search filter if provided
    if search:
        from gci.core.search import GPTSearcher

        searcher = GPTSearcher(workspace_id)
        # Convert back to dicts for searcher (it expects dicts)
        gpts_as_dicts = [gpt.model_dump() for gpt in gpts_data]
        filtered_dicts = searcher.filter_and_search(gpts_as_dicts, search_query=search)
        # Convert back to models
        gpts_data = [GPT.model_validate(d) for d in filtered_dicts]
        console.print(f"[dim]Filtered to {len(gpts_data)} GPTs matching '{search}'[/dim]")

    # Filter out GPTs without files (they're Low risk by default)
    # This needs to be done before applying limit
    gpts_with_files: list[GPT] = []
    skipped_count = 0

    for gpt in gpts_data:
        # Use GPT model property to get files
        if gpt.files:  # This uses the GPT.files property which returns list[GPTFile]
            gpts_with_files.append(gpt)
            # Apply limit to GPTs with files
            if limit and len(gpts_with_files) >= limit:
                break
        else:
            skipped_count += 1

    if skipped_count > 0:
        console.print(f"[dim]Skipped {skipped_count} GPTs without files[/dim]")

    gpts_data = gpts_with_files

    if limit and len(gpts_data) == limit:
        console.print(f"[dim]Limited to {limit} GPTs with files for classification[/dim]")

    if not gpts_data:
        console.print("[yellow]No GPTs with files found to classify.[/yellow]")
        raise typer.Exit(0)

    # Initialize LLM client
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

    # Validate LLM connection before processing
    console.print("[dim]Validating LLM connection...[/dim]")
    try:
        llm_client.validate()
        console.print("[green]✓ LLM connection validated[/green]")
    except Exception as e:
        console.print(f"[red]Error: LLM validation failed: {e}[/red]")
        if llm_provider == "bedrock":
            console.print("[dim]For AWS Bedrock, ensure AWS_PROFILE is set[/dim]")
        raise typer.Exit(1) from e

    # Initialize cache and service
    risk_cache = RiskClassificationCache(workspace_id)
    classifier_service = RiskClassificationService(llm_client)

    # Prepare GPT data for classification
    gpt_classification_data = []
    for gpt in gpts_data:
        # Use GPT model properties
        gpt_id = gpt.id
        gpt_name = gpt.name or "Unnamed GPT"
        # Extract file names from GPT model
        file_names = [f.name for f in gpt.files if f.name]
        gpt_classification_data.append((gpt_id, gpt_name, file_names))

    # Check cache for existing classifications (unless --no-cache)
    all_classifications = []
    remaining_gpts = gpt_classification_data

    if not no_cache:
        console.print("[dim]Checking cache for existing classifications...[/dim]")
        cached_classifications, remaining_gpts = risk_cache.get_batch_classifications(
            gpt_classification_data, llm_client.model, llm_client.provider
        )
        all_classifications.extend(cached_classifications)

        if cached_classifications:
            console.print(f"[dim]Found {len(cached_classifications)} cached classifications[/dim]")

    # Process remaining GPTs in batches
    if remaining_gpts:
        total_batches = (len(remaining_gpts) + batch_size - 1) // batch_size

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Classifying GPTs...", total=len(remaining_gpts))

            for i in range(0, len(remaining_gpts), batch_size):
                batch_data = remaining_gpts[i : i + batch_size]
                batch_num = (i // batch_size) + 1

                progress.update(task, description=f"Classifying batch {batch_num}/{total_batches}...")

                try:
                    batch_classifications = classifier_service.classify_batch(batch_data)
                    all_classifications.extend(batch_classifications)

                    # Cache the new classifications
                    if not no_cache:
                        risk_cache.save_batch_classifications(
                            batch_classifications, batch_data, llm_client.model, llm_client.provider
                        )

                    progress.update(task, advance=len(batch_data))

                except Exception as e:
                    logger.error(f"Error processing batch {batch_num}: {e}")
                    # Continue with remaining batches
                    progress.update(task, advance=len(batch_data))
    else:
        console.print("[dim]All classifications found in cache[/dim]")

    # Create final batch result
    result_batch = RiskClassificationBatch(classifications=all_classifications)

    # Handle output
    if output_format == RiskOutputFormat.TABLE:
        handle_table_output(result_batch, search)
    elif output_format == RiskOutputFormat.JSON:
        handle_json_output(
            transform_batch_for_json(result_batch),
            output,
        )
    elif output_format == RiskOutputFormat.CSV:
        handle_csv_output(
            result_batch.classifications,
            output,
            fieldnames=["gpt_id", "gpt_name", "file_names", "risk_level", "reasoning", "classified_at"],
            row_transformer=transform_classification_for_csv,
        )

    # Show timing info
    elapsed = datetime.now() - start_time
    console.print(f"\n[dim]Completed in {elapsed.total_seconds():.1f}s[/dim]")
