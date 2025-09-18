"""Utility functions for CLI commands."""

import typer
from rich.console import Console

from ...api.client import ComplianceAPIClient
from ...config import load_config

console = Console()


def with_api_client(
    api_key: str,
    workspace_id: str,
    validate_credentials: bool = True,
) -> ComplianceAPIClient:
    """Context manager helper for API client initialization.

    Args:
        api_key: OpenAI API key
        workspace_id: OpenAI workspace ID
        validate_credentials: Whether to validate credentials on connection

    Returns:
        Initialized API client

    Note: This is a helper that returns the client, not a context manager itself.
          Use with regular 'with' statement in the calling code.
    """
    client = ComplianceAPIClient(api_key, workspace_id)
    if validate_credentials:
        with console.status("[bold blue]Connecting to API...[/bold blue]", spinner="dots"), client:
            # Temporarily open a session just for validation
            client.validate_credentials()
            console.print("[green]✓ Connected[/green]")

    return client


def get_api_credentials(
    api_key: str | None = None,
    workspace_id: str | None = None,
) -> tuple[str, str]:
    """Get API credentials from parameters or environment/prompts.

    Args:
        api_key: Optional API key override
        workspace_id: Optional workspace ID override

    Returns:
        Tuple of (api_key, workspace_id)

    Note:
        This function only reads credentials from environment variables
        or prompts the user. It does not save credentials to any config file.
    """
    config = load_config()

    # Get workspace ID first (from parameter, environment, or prompt)
    final_workspace_id = workspace_id or config.workspace_id
    if not final_workspace_id:
        final_workspace_id = typer.prompt("OpenAI Workspace ID")

    # Get API key (from parameter, environment, or prompt)
    final_api_key = api_key
    if not final_api_key and config.api_key:
        final_api_key = config.api_key.get_secret_value()
    if not final_api_key:
        final_api_key = typer.prompt(
            "OpenAI API Key",
            hide_input=True,
            confirmation_prompt=False,
        )

    return final_api_key, final_workspace_id
