"""OpenAI Compliance API client implementation."""

import logging
import os
import time
from typing import Any, Generic, TypeVar

import backoff
import requests
from pydantic import BaseModel
from rich.console import Console
from tqdm import tqdm

from gci.cache import GPTCache
from gci.core.constants import API_BASE_URL, APIConstants, ProgressBarConstants
from gci.exceptions import (
    APIError,
    AuthenticationError,
    InvalidCredentialsError,
    NotFoundError,
    PermissionError,
    RateLimitError,
    TimeoutError,
    ValidationError,
)
from gci.models.gpt import GPT

T = TypeVar("T")


class ListResponse(BaseModel, Generic[T]):
    """Generic list response from Compliance API."""

    object: str
    data: list[T]
    has_more: bool = False
    last_id: str | None = None


class ComplianceAPIClient:
    """Client for interacting with OpenAI Compliance API."""

    def __init__(self, api_key: str | None = None, workspace_id: str | None = None) -> None:
        """Initialize the API client.

        Args:
            api_key: OpenAI API key for authentication (defaults to GCI_OPENAI_API_KEY env var)
            workspace_id: Workspace ID to query (defaults to GCI_OPENAI_WORKSPACE_ID env var)

        Raises:
            InvalidCredentialsError: If API key format is invalid
            ValidationError: If workspace ID format is invalid

        """
        # Create logger instance for this class
        self.logger = logging.getLogger(__name__)
        self.console = Console()

        self.api_key = api_key or os.getenv("GCI_OPENAI_API_KEY")
        self.workspace_id = workspace_id or os.getenv("GCI_OPENAI_WORKSPACE_ID")

        self.logger.info("Initializing ComplianceAPIClient")
        self.logger.debug(f"Workspace ID: {self.workspace_id}")

        if not self.api_key:
            self.logger.error("API key not provided")
            raise InvalidCredentialsError("API key")

        if not self.workspace_id:
            self.logger.error("Workspace ID not provided")
            raise ValidationError(
                "workspace_id",
                None,
                "Workspace ID must be provided either as parameter or via GCI_OPENAI_WORKSPACE_ID environment variable",
            )

        self.base_url = API_BASE_URL
        self.session: requests.Session | None = None
        self.logger.info("ComplianceAPIClient initialized successfully")

    def __enter__(self) -> "ComplianceAPIClient":
        """Enter context."""
        self.logger.info("Opening client session")
        self.session = requests.Session()
        self.logger.debug("Client session opened successfully")
        return self

    def __exit__(self, *args: Any) -> None:
        """Exit context."""
        self.logger.info("Closing client session")
        if self.session:
            self.session.close()
            self.logger.debug("Client session closed successfully")
        else:
            self.logger.warning("No session to close")

    @property
    def headers(self) -> dict[str, str]:
        """Get request headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    @backoff.on_exception(
        backoff.expo,
        (requests.exceptions.RequestException,),
        max_tries=APIConstants.BACKOFF_MAX_TRIES,
        factor=APIConstants.BACKOFF_FACTOR,
        max_value=APIConstants.BACKOFF_MAX_VALUE,
    )
    def _make_request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Make an API request with retry logic.

        Args:
            method: HTTP method
            endpoint: API endpoint path
            params: Query parameters

        Returns:
            Response data

        """
        if not self.session:
            raise RuntimeError("Client not initialized. Use context manager.")

        url = f"{self.base_url}{endpoint}"
        method_name = f"{method} {endpoint}"

        self.logger.debug(f"Making request: {method_name}")

        response = self.session.request(
            method, url, headers=self.headers, params=params, timeout=APIConstants.REQUEST_TIMEOUT
        )

        if response.status_code == 200:
            return response.json()

        response_text = response.text

        # Map status codes to exceptions
        error_map = {
            401: lambda: AuthenticationError(f"Unauthorized access in {method_name}", response_text),
            403: lambda: PermissionError(f"Access forbidden in {method_name}", response_text),
            404: lambda: NotFoundError(f"Resource not found in {method_name}", response_text),
            408: lambda: TimeoutError(method_name, APIConstants.REQUEST_TIMEOUT),
            429: lambda: RateLimitError(
                f"Rate limit exceeded in {method_name}",
                response_text,
                int(response.headers.get("Retry-After", 0)) if response.headers.get("Retry-After") else None,
            ),
        }

        # Check for specific error or server error
        if response.status_code in error_map:
            raise error_map[response.status_code]()
        elif 500 <= response.status_code < 600:
            raise APIError(response.status_code, f"Server error in {method_name}", response_text)
        else:
            raise APIError(
                response.status_code,
                f"Unexpected response status {response.status_code} in {method_name}",
                response_text,
            )

    def validate_credentials(self) -> None:
        """Validate API credentials by making a test request without retries.

        Raises:
            requests.HTTPError: If credentials are invalid or API is unreachable

        """
        # Create a separate session for validation without retries
        with requests.Session() as validation_session:
            url = f"{self.base_url}/compliance/workspaces/{self.workspace_id}/gpts"
            try:
                response = validation_session.get(
                    url,
                    headers=self.headers,
                    params={"limit": APIConstants.VALIDATION_PAGE_LIMIT},
                    timeout=APIConstants.REQUEST_TIMEOUT,
                )
                if response.status_code == 401:
                    raise InvalidCredentialsError("API key")
                elif response.status_code == 403:
                    raise PermissionError(
                        f"Access denied for workspace '{self.workspace_id}'. "
                        "Please check your workspace ID and permissions."
                    )
                elif response.status_code == 404:
                    raise ValueError(f"Workspace '{self.workspace_id}' not found. Please check your workspace ID.")
                response.raise_for_status()
            except requests.RequestException as e:
                if hasattr(e, "response") and e.response is not None:
                    raise
                raise requests.RequestException(f"Failed to connect to OpenAI API: {e}") from e

    def _load_cached_data(self, cache: GPTCache, resume_from: str) -> tuple[list[dict[str, Any]], int, str | None]:
        """Load cached data when resuming."""
        checkpoint = cache.load_checkpoint()
        if not checkpoint:
            return [], 0, None

        self.console.print(f"[yellow]Resuming from page {checkpoint.last_page}[/yellow]")
        results = cache.load_cached_pages(checkpoint.last_page)
        cursor = results[-1]["id"] if results else resume_from
        return results, checkpoint.last_page, cursor

    def _fetch_page(self, endpoint: str, params: dict[str, Any]) -> ListResponse[dict[str, Any]]:
        """Fetch a single page of results."""
        try:
            data = self._make_request("GET", endpoint, params=params)
            return ListResponse[dict[str, Any]](**data)
        except requests.exceptions.Timeout:
            raise TimeoutError("Request timeout", APIConstants.REQUEST_TIMEOUT) from None

    def _save_to_cache(
        self, cache: GPTCache, page: int, data: list[dict[str, Any]], last_id: str, total_results: int
    ) -> None:
        """Save page data to cache."""
        if cache and data and last_id:
            cache.save_page(page, data, last_id)
            cache.save_checkpoint(last_id, page, total_results)

    def _paginate(
        self,
        endpoint: str,
        params: dict[str, Any] | None = None,
        cache_key: str | None = None,
        resume_from: str | None = None,
    ) -> list[dict[str, Any]]:
        """Paginate through API results."""
        params = params or {}
        results = []
        cursor = resume_from
        page = 0
        start_time = time.time()

        cache = GPTCache(cache_key) if cache_key else None

        # Create progress bar
        pbar = tqdm(
            desc="Fetching GPTs",
            unit=" GPTs",
            mininterval=ProgressBarConstants.MIN_UPDATE_INTERVAL,
            maxinterval=ProgressBarConstants.MAX_UPDATE_INTERVAL,
        )

        # Load cached data if resuming
        if cache and resume_from:
            results, page, cursor = self._load_cached_data(cache, resume_from)
            if results:
                pbar.n = len(results)
                pbar.refresh()

        # Fetch pages
        while True:
            if cursor:
                params["after"] = cursor

            response = self._fetch_page(endpoint, params)
            results.extend(response.data)
            page += 1

            # Update progress
            pbar.update(len(response.data))
            if response.last_id:
                short_id = response.last_id[:8] if len(response.last_id) > 8 else response.last_id
                pbar.set_postfix({"id": short_id})

            # Save to cache
            if cache and response.data and response.last_id:
                self._save_to_cache(cache, page, response.data, response.last_id, len(results))

            if not response.has_more or not response.last_id:
                break

            cursor = response.last_id

        pbar.close()

        # Final cache operations
        if cache and results:
            cache.save_complete_results(results, page)
            cache.remove_checkpoint()

        total_time = time.time() - start_time
        self.console.print(f"\n[dim]Fetched {len(results)} items in {total_time:.1f}s[/dim]")

        return results

    def list_gpts(self, resume_from: str | None = None) -> list[GPT]:
        """List all GPTs in the workspace.

        Returns:
            List of GPT summaries

        """
        endpoint = f"/compliance/workspaces/{self.workspace_id}/gpts"
        self.logger.info("Fetching GPTs list")

        # Use larger page size for efficiency
        gpts_data = self._paginate(
            endpoint,
            params={"limit": APIConstants.DEFAULT_PAGE_SIZE},
            cache_key=self.workspace_id,
            resume_from=resume_from,
        )
        gpts = [GPT(**item) for item in gpts_data]

        self.logger.info(f"Found {len(gpts)} GPTs")
        return gpts

    def get_gpt_config(self, gpt_id: str) -> dict[str, Any]:
        """Get detailed configuration for a specific GPT.

        Args:
            gpt_id: The GPT ID to fetch configuration for

        Returns:
            GPT configuration data

        """
        endpoint = f"/compliance/workspaces/{self.workspace_id}/gpts/{gpt_id}/configs"
        self.logger.info(f"Fetching configuration for GPT {gpt_id}")

        data = self._make_request("GET", endpoint)
        self.logger.debug(f"Got configuration for GPT {gpt_id}")
        return data

    def get_gpt_shared_users(self, gpt_id: str) -> list[dict[str, Any]]:
        """Get list of users who have access to a specific GPT.

        Args:
            gpt_id: The GPT ID to fetch shared users for

        Returns:
            List of shared users

        """
        endpoint = f"/compliance/workspaces/{self.workspace_id}/gpts/{gpt_id}/shared_users"
        self.logger.info(f"Fetching shared users for GPT {gpt_id}")

        # This endpoint might also be paginated
        users_data = self._paginate(endpoint, params={"limit": APIConstants.DEFAULT_PAGE_SIZE})
        self.logger.debug(f"Got {len(users_data)} shared users for GPT {gpt_id}")
        return users_data
