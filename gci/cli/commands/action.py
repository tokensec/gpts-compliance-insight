"""Custom actions analyzer command implementation."""

import logging
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any

import typer
from rich.console import Console
from rich.progress import BarColumn, MofNCompleteColumn, Progress, SpinnerColumn, TextColumn
from rich.table import Table

from gci.cache.action import ActionAnalysisCache
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
from gci.models.action import ActionAnalysisBatch, ActionCapability, GPTActionAnalysis
from gci.models.gpt import GPT, GPTTool
from gci.services.action_analyzer import ActionAnalyzerService


class ActionOutputFormat(StrEnum):
    """Output formats for custom actions analyzer."""

    TABLE = "table"
    JSON = "json"
    CSV = "csv"


console = Console()
logger = logging.getLogger(__name__)


def handle_table_output(batch: ActionAnalysisBatch, search_query: str | None = None) -> None:  # noqa: ARG001
    """Handle table format output."""
    table = Table(title="GPT Custom Actions Analysis", show_lines=True)

    table.add_column("Level", style="bold", width=8, justify="center")
    table.add_column("GPT Name", style="cyan", min_width=20)
    table.add_column("Action Name", style="yellow", min_width=15)
    table.add_column("Domain", style="blue", min_width=20)
    table.add_column("Auth", style="magenta", width=10)
    table.add_column("Capabilities", min_width=30)

    # Sort by capability level (Critical -> Moderate -> Minimal) then by GPT name
    level_order = {ActionCapability.CRITICAL: 0, ActionCapability.MODERATE: 1, ActionCapability.MINIMAL: 2}
    sorted_analyses = sorted(
        batch.analyses, key=lambda x: (level_order[x.capability_level], x.gpt_name.lower(), x.action_name.lower())
    )

    for analysis in sorted_analyses:
        level_display = f"{analysis.capability_emoji} {analysis.capability_level.value}"

        table.add_row(
            level_display,
            analysis.gpt_name,
            analysis.action_name,
            analysis.domain,
            analysis.auth_type,
            analysis.capabilities_summary,
        )

    console.print(table)

    # Print summary
    summary = batch.summary
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"🔴 Critical: {summary['critical']}")
    console.print(f"🟡 Moderate: {summary['moderate']}")
    console.print(f"🟢 Minimal: {summary['minimal']}")
    console.print(f"📊 Total Actions: {summary['total_actions']}")
    console.print(f"📦 Total GPTs: {summary['total_gpts']}")

    if summary["auth_types"]:
        console.print("\n[bold]Authentication Types:[/bold]")
        for auth_type, count in summary["auth_types"].items():
            console.print(f"  🔐 {auth_type}: {count}")


def transform_batch_for_json(batch: ActionAnalysisBatch) -> dict[str, Any]:
    """Transform action analysis batch for JSON output."""
    return {
        "summary": batch.summary,
        "processed_at": batch.processed_at.isoformat(),
        "analyses": [
            {
                "gpt_id": a.gpt_id,
                "gpt_name": a.gpt_name,
                "action_name": a.action_name,
                "domain": a.domain,
                "auth_type": a.auth_type,
                "primary_path": a.primary_path,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                "capabilities_summary": a.capabilities_summary,
                "capability_level": a.capability_level.value,
                "analyzed_at": a.analyzed_at.isoformat(),
            }
            for a in batch.analyses
        ],
    }


def transform_analysis_for_csv(analysis: GPTActionAnalysis) -> dict[str, Any]:
    """Transform a single analysis for CSV output."""
    return {
        "gpt_id": analysis.gpt_id,
        "gpt_name": analysis.gpt_name,
        "action_name": analysis.action_name,
        "domain": analysis.domain,
        "auth_type": analysis.auth_type,
        "primary_path": analysis.primary_path,
        "capabilities_summary": analysis.capabilities_summary,
        "capability_level": analysis.capability_level.value,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else "",
        "analyzed_at": analysis.analyzed_at.isoformat(),
    }


def custom_actions(
    workspace_id: WORKSPACE_ID_OPTION = None,
    output_format: Annotated[
        ActionOutputFormat,
        typer.Option(
            "--format",
            "-f",
            help="Output format",
            case_sensitive=False,
        ),
    ] = ActionOutputFormat.TABLE,
    output: OUTPUT_PATH_OPTION = None,
    search: SEARCH_OPTION = None,
    limit: Annotated[
        int | None,
        typer.Option(
            "--limit",
            "-l",
            help="Limit number of GPTs to analyze (useful for testing)",
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
            help="Number of actions to process per LLM call",
            min=1,
            max=20,
        ),
    ] = 5,
    no_download: NO_DOWNLOAD_OPTION = False,
    no_cache: Annotated[
        bool,
        typer.Option(
            "--no-cache",
            help="Skip cached action analyses and reanalyze all actions",
        ),
    ] = False,
) -> None:
    """Analyze custom actions in GPTs and summarize their capabilities.

    This command extracts custom actions from GPT configurations, parses their
    OpenAPI specifications, and uses an LLM to analyze and summarize what each
    action can do.

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
    gpts_raw = cache_result.data
    gpts_data: list[GPT] = []

    for gpt_dict in gpts_raw:
        try:
            gpt_model = GPT.model_validate(gpt_dict)
            gpts_data.append(gpt_model)
        except Exception as e:
            logger.warning(f"Failed to parse GPT: {e}")
            continue

    console.print(f"[dim]Loaded {len(gpts_data)} GPTs from cache[/dim]")

    # Apply search filter if provided
    if search:
        from gci.core.search import GPTSearcher

        searcher = GPTSearcher(workspace_id)
        gpts_as_dicts = [gpt.model_dump() for gpt in gpts_data]
        filtered_dicts = searcher.filter_and_search(gpts_as_dicts, search_query=search)
        gpts_data = [GPT.model_validate(d) for d in filtered_dicts]
        console.print(f"[dim]Filtered to {len(gpts_data)} GPTs matching '{search}'[/dim]")

    # Extract GPTs with custom actions
    gpts_with_actions: list[tuple[GPT, list[GPTTool]]] = []
    skipped_count = 0

    for gpt in gpts_data:
        custom_actions = ActionAnalyzerService.extract_custom_actions_from_gpt(gpt)
        if custom_actions:
            gpts_with_actions.append((gpt, custom_actions))
            # Apply limit to GPTs with actions
            if limit and len(gpts_with_actions) >= limit:
                break
        else:
            skipped_count += 1

    if skipped_count > 0:
        console.print(f"[dim]Skipped {skipped_count} GPTs without custom actions[/dim]")

    if limit and len(gpts_with_actions) == limit:
        console.print(f"[dim]Limited to {limit} GPTs with custom actions for analysis[/dim]")

    if not gpts_with_actions:
        console.print("[yellow]No GPTs with custom actions found to analyze.[/yellow]")
        raise typer.Exit(0)

    # Count total actions
    total_actions = sum(len(actions) for _, actions in gpts_with_actions)
    console.print(f"[dim]Found {total_actions} custom actions across {len(gpts_with_actions)} GPTs[/dim]")

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

    # Initialize cache and service
    action_cache = ActionAnalysisCache(workspace_id)
    analyzer_service = ActionAnalyzerService(llm_client)

    # Prepare data for caching
    actions_data_for_cache: list[tuple[str, str, str]] = []

    for gpt, actions in gpts_with_actions:
        for action in actions:
            actions_data_for_cache.append((gpt.id, gpt.name or "Unnamed", action.action_domain or "unknown"))

    # Check cache for existing analyses (unless --no-cache)
    all_analyses: list[GPTActionAnalysis] = []
    remaining_actions = gpts_with_actions

    if not no_cache:
        console.print("[dim]Checking cache for existing analyses...[/dim]")
        cached_analyses, uncached_data = action_cache.get_batch_analyses(
            actions_data_for_cache, llm_client.model, llm_client.provider
        )
        all_analyses.extend(cached_analyses)

        if cached_analyses:
            console.print(f"[dim]Found {len(cached_analyses)} cached analyses[/dim]")

        # Rebuild remaining_actions based on uncached data
        remaining_actions = []
        for gpt, actions in gpts_with_actions:
            uncached_actions = []
            for action in actions:
                action_key = (gpt.id, gpt.name or "Unnamed", action.action_domain or "unknown")
                if action_key in uncached_data:
                    uncached_actions.append(action)
            if uncached_actions:
                remaining_actions.append((gpt, uncached_actions))

    # Process remaining actions in batches
    if remaining_actions:
        # Flatten for progress tracking
        total_remaining = sum(len(actions) for _, actions in remaining_actions)
        total_batches = (total_remaining + batch_size - 1) // batch_size

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            MofNCompleteColumn(),
            console=console,
        ) as progress:
            task = progress.add_task("Analyzing custom actions...", total=total_remaining)

            # Process in batches
            batch_buffer: list[tuple[GPT, list[GPTTool]]] = []
            batch_action_count = 0
            batch_num = 0

            for gpt, actions in remaining_actions:
                for action in actions:
                    batch_buffer.append((gpt, [action]))
                    batch_action_count += 1

                    if batch_action_count >= batch_size:
                        # Process this batch
                        batch_num += 1
                        progress.update(task, description=f"Analyzing batch {batch_num}/{total_batches}...")

                        try:
                            batch_analyses = analyzer_service.analyze_batch(batch_buffer)
                            all_analyses.extend(batch_analyses)

                            # Cache the new analyses
                            if not no_cache:
                                action_cache.save_batch_analyses(batch_analyses, llm_client.model, llm_client.provider)

                            progress.update(task, advance=batch_action_count)

                        except Exception as e:
                            logger.error(f"Error processing batch {batch_num}: {e}")
                            progress.update(task, advance=batch_action_count)

                        # Reset batch buffer
                        batch_buffer = []
                        batch_action_count = 0

            # Process remaining items in buffer
            if batch_buffer:
                batch_num += 1
                progress.update(task, description=f"Analyzing batch {batch_num}/{total_batches}...")

                try:
                    batch_analyses = analyzer_service.analyze_batch(batch_buffer)
                    all_analyses.extend(batch_analyses)

                    # Cache the new analyses
                    if not no_cache:
                        action_cache.save_batch_analyses(batch_analyses, llm_client.model, llm_client.provider)

                    progress.update(task, advance=batch_action_count)

                except Exception as e:
                    logger.error(f"Error processing final batch: {e}")
                    progress.update(task, advance=batch_action_count)
    else:
        console.print("[dim]All analyses found in cache[/dim]")

    # Create final batch result
    result_batch = ActionAnalysisBatch(analyses=all_analyses)

    # Handle output
    if output_format == ActionOutputFormat.TABLE:
        handle_table_output(result_batch, search)
    elif output_format == ActionOutputFormat.JSON:
        handle_json_output(
            transform_batch_for_json(result_batch),
            output,
        )
    elif output_format == ActionOutputFormat.CSV:
        handle_csv_output(
            result_batch.analyses,
            output,
            fieldnames=[
                "gpt_id",
                "gpt_name",
                "action_name",
                "domain",
                "auth_type",
                "primary_path",
                "capabilities_summary",
                "capability_level",
                "created_at",
                "analyzed_at",
            ],
            row_transformer=transform_analysis_for_csv,
        )

    # Show timing info
    elapsed = datetime.now() - start_time
    console.print(f"\n[dim]Completed in {elapsed.total_seconds():.1f}s[/dim]")
