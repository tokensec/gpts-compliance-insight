"""Custom action analysis data models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ActionCapability(StrEnum):
    """Action capability/risk levels."""

    CRITICAL = "Critical"
    MODERATE = "Moderate"
    MINIMAL = "Minimal"


class GPTActionAnalysis(BaseModel):
    """Analysis of custom actions for a single GPT."""

    gpt_id: str = Field(description="GPT identifier")
    gpt_name: str = Field(description="GPT name")
    action_name: str = Field(description="Name of the custom action")
    domain: str = Field(description="API domain/server URL")
    auth_type: str = Field(default="unknown", description="Authentication type")
    primary_path: str = Field(default="", description="Primary API path")
    created_at: datetime | None = Field(default=None, description="When action was created")
    capabilities_summary: str = Field(description="Natural language summary of action capabilities")
    capability_level: ActionCapability = Field(description="Capability/risk assessment level")
    analyzed_at: datetime = Field(default_factory=lambda: datetime.now(UTC), description="Timestamp of analysis")

    @property
    def capability_color(self) -> str:
        """Get Rich color for the capability level."""
        color_map = {
            ActionCapability.CRITICAL: "red",
            ActionCapability.MODERATE: "yellow",
            ActionCapability.MINIMAL: "green",
        }
        return color_map.get(self.capability_level, "white")

    @property
    def capability_emoji(self) -> str:
        """Get emoji for the capability level."""
        emoji_map = {
            ActionCapability.CRITICAL: "🔴",
            ActionCapability.MODERATE: "🟡",
            ActionCapability.MINIMAL: "🟢",
        }
        return emoji_map.get(self.capability_level, "⚪")


class ActionAnalysisBatch(BaseModel):
    """Batch of action analyses."""

    analyses: list[GPTActionAnalysis] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_gpts(self) -> int:
        """Number of unique GPTs analyzed."""
        return len({a.gpt_id for a in self.analyses})

    @property
    def total_actions(self) -> int:
        """Total number of custom actions analyzed."""
        return len(self.analyses)

    @property
    def critical_count(self) -> int:
        """Number of critical capability actions."""
        return sum(1 for a in self.analyses if a.capability_level == ActionCapability.CRITICAL)

    @property
    def moderate_count(self) -> int:
        """Number of moderate capability actions."""
        return sum(1 for a in self.analyses if a.capability_level == ActionCapability.MODERATE)

    @property
    def minimal_count(self) -> int:
        """Number of minimal capability actions."""
        return sum(1 for a in self.analyses if a.capability_level == ActionCapability.MINIMAL)

    @property
    def auth_type_counts(self) -> dict[str, int]:
        """Count of actions by authentication type."""
        auth_counts: dict[str, int] = {}
        for analysis in self.analyses:
            auth_type = analysis.auth_type or "unknown"
            auth_counts[auth_type] = auth_counts.get(auth_type, 0) + 1
        return auth_counts

    @property
    def summary(self) -> dict[str, Any]:
        """Summary statistics."""
        return {
            "total_gpts": self.total_gpts,
            "total_actions": self.total_actions,
            "critical": self.critical_count,
            "moderate": self.moderate_count,
            "minimal": self.minimal_count,
            "auth_types": self.auth_type_counts,
        }


class ActionAnalysisError(BaseModel):
    """Error that occurred during action analysis."""

    gpt_id: str = Field(description="GPT identifier where error occurred")
    gpt_name: str = Field(description="GPT name")
    error_message: str = Field(description="Error description")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Models for Instructor (LLM response parsing)
class ActionAnalysisResponse(BaseModel):
    """Single action analysis from LLM response."""

    action_name: str = Field(description="Name of the custom action")
    domain: str = Field(description="API domain or server URL")
    auth_type: str = Field(default="unknown", description="Authentication type")
    primary_path: str = Field(default="", description="Primary API path")
    capabilities_summary: str = Field(description="Natural language summary of what the action can do")
    capability_level: Literal["Critical", "Moderate", "Minimal"] = Field(description="Capability/risk assessment level")


class BatchActionResponse(BaseModel):
    """Batch of action analyses from LLM response."""

    analyses: list[ActionAnalysisResponse] = Field(description="List of custom action analyses")
