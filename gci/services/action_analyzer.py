"""Action analysis service using Instructor for structured outputs."""

import json
import logging
from datetime import datetime
from typing import Any

from gci.llm.client import LLMClient
from gci.llm.prompts import create_action_analysis_messages
from gci.models.action import ActionCapability, BatchActionResponse, GPTActionAnalysis
from gci.models.gpt import GPT, GPTTool

logger = logging.getLogger(__name__)


class ActionAnalyzerService:
    """Service for analyzing custom actions in GPTs."""

    def __init__(self, llm_client: LLMClient) -> None:
        """Initialize action analyzer service.

        Args:
            llm_client: LLM client for making analysis requests
        """
        self.llm_client = llm_client

    def analyze_batch(
        self,
        gpts_with_actions: list[tuple[GPT, list[GPTTool]]],
    ) -> list[GPTActionAnalysis]:
        """Analyze a batch of GPTs with custom actions.

        Args:
            gpts_with_actions: List of (GPT, list of custom action tools) tuples

        Returns:
            List of action analyses
        """
        if not gpts_with_actions:
            return []

        # Prepare action info for LLM
        actions_info_parts = []
        action_metadata: list[tuple[str, str, GPTTool]] = []

        for gpt, tools in gpts_with_actions:
            for tool in tools:
                # Parse OpenAPI spec if available
                openapi_data = self._parse_openapi(tool.action_openapi_raw)

                # Build action info for prompt
                action_info = f"GPT Name: {gpt.name or 'Unnamed'}\n"
                action_info += f"Action Domain: {tool.action_domain or 'unknown'}\n"
                action_info += f"Auth Type: {tool.auth_type or 'unknown'}\n"

                if openapi_data:
                    action_info += f"OpenAPI Info:\n{json.dumps(openapi_data, indent=2)}\n"
                else:
                    action_info += "OpenAPI: Not available or invalid\n"

                actions_info_parts.append(action_info)
                action_metadata.append((gpt.id, gpt.name or "Unnamed", tool))

        actions_info = "\n---\n".join(actions_info_parts)

        # Create messages for LLM
        messages = create_action_analysis_messages(actions_info)

        logger.debug(f"Analyzing batch of {len(action_metadata)} custom actions")

        try:
            # Get structured response using Instructor
            response = self.llm_client.complete(messages=messages, response_model=BatchActionResponse)

            # Convert to storage format
            results = []
            for i, analysis in enumerate(response.analyses):
                if i < len(action_metadata):
                    gpt_id, gpt_name, tool = action_metadata[i]

                    # Convert created_at timestamp if available
                    created_at = None
                    if tool.created_at:
                        created_at = datetime.fromtimestamp(tool.created_at)

                    results.append(
                        GPTActionAnalysis(
                            gpt_id=gpt_id,
                            gpt_name=gpt_name,
                            action_name=analysis.action_name,
                            domain=analysis.domain,
                            auth_type=analysis.auth_type,
                            primary_path=analysis.primary_path,
                            created_at=created_at,
                            capabilities_summary=analysis.capabilities_summary,
                            capability_level=ActionCapability(analysis.capability_level),
                        )
                    )

            logger.debug(f"Successfully analyzed {len(results)} custom actions")
            return results

        except Exception as e:
            logger.error(f"Error analyzing batch: {e}")
            # Return minimal analyses with error info
            return [
                GPTActionAnalysis(
                    gpt_id=gpt_id,
                    gpt_name=gpt_name,
                    action_name=f"Action from {tool.action_domain or 'unknown'}",
                    domain=tool.action_domain or "unknown",
                    auth_type=tool.auth_type or "unknown",
                    primary_path="",
                    created_at=datetime.fromtimestamp(tool.created_at) if tool.created_at else None,
                    capabilities_summary=f"Analysis failed: {e!s}",
                    capability_level=ActionCapability.MINIMAL,
                )
                for gpt_id, gpt_name, tool in action_metadata
            ]

    @staticmethod
    def _parse_openapi(openapi_raw: str | None) -> dict[str, Any] | None:
        """Safely parse OpenAPI specification.

        Args:
            openapi_raw: Raw OpenAPI specification string

        Returns:
            Parsed OpenAPI data or None if invalid
        """
        if not openapi_raw:
            return None

        try:
            data = json.loads(openapi_raw)

            # Extract key information
            result: dict[str, Any] = {}

            # Get basic info
            if "info" in data:
                result["title"] = data["info"].get("title", "Unknown API")
                result["description"] = data["info"].get("description", "")

            # Get server URLs
            if data.get("servers"):
                result["servers"] = [s.get("url", "") for s in data["servers"]]

            # Get paths summary
            if "paths" in data:
                result["endpoints"] = []
                for path, methods in data["paths"].items():
                    if isinstance(methods, dict):
                        for method in methods:
                            if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
                                result["endpoints"].append(f"{method.upper()} {path}")

            # Get security schemes
            if "components" in data and "securitySchemes" in data["components"]:
                result["security"] = list(data["components"]["securitySchemes"].keys())

            return result

        except (json.JSONDecodeError, TypeError, KeyError) as e:
            logger.debug(f"Failed to parse OpenAPI spec: {e}")
            return None

    @staticmethod
    def extract_custom_actions_from_gpt(gpt: GPT) -> list[GPTTool]:
        """Extract custom action tools from a GPT.

        Args:
            gpt: GPT model instance

        Returns:
            List of custom action tools
        """
        return [tool for tool in gpt.tools if tool.is_custom_action]
