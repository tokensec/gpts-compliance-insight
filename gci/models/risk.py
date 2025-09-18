"""Risk classification data models."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RiskLevel(StrEnum):
    """Risk classification levels."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class GPTRiskClassification(BaseModel):
    """Risk classification for a single GPT."""

    gpt_id: str = Field(description="GPT identifier")
    gpt_name: str = Field(description="GPT name")
    file_names: list[str] = Field(default_factory=list, description="List of file names associated with GPT")
    risk_level: RiskLevel = Field(description="Classified risk level")
    reasoning: str = Field(description="Explanation for the risk classification")
    classified_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC), description="Timestamp of classification"
    )

    @field_validator("file_names", mode="before")
    @classmethod
    def ensure_list(cls, v: Any) -> list[str]:
        """Ensure file_names is always a list."""
        if v is None:
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []

    @property
    def file_names_str(self) -> str:
        """Get file names as a comma-separated string."""
        return ", ".join(self.file_names) if self.file_names else "No files"

    @property
    def risk_color(self) -> str:
        """Get Rich color for the risk level."""
        color_map = {
            RiskLevel.HIGH: "red",
            RiskLevel.MEDIUM: "yellow",
            RiskLevel.LOW: "green",
        }
        return color_map.get(self.risk_level, "white")

    @property
    def risk_emoji(self) -> str:
        """Get emoji for the risk level."""
        emoji_map = {
            RiskLevel.HIGH: "🔴",
            RiskLevel.MEDIUM: "🟡",
            RiskLevel.LOW: "🟢",
        }
        return emoji_map.get(self.risk_level, "⚪")


class RiskClassificationBatch(BaseModel):
    """Batch of risk classifications."""

    classifications: list[GPTRiskClassification] = Field(default_factory=list)
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def total_count(self) -> int:
        """Total number of classifications."""
        return len(self.classifications)

    @property
    def high_risk_count(self) -> int:
        """Number of high-risk GPTs."""
        return sum(1 for c in self.classifications if c.risk_level == RiskLevel.HIGH)

    @property
    def medium_risk_count(self) -> int:
        """Number of medium-risk GPTs."""
        return sum(1 for c in self.classifications if c.risk_level == RiskLevel.MEDIUM)

    @property
    def low_risk_count(self) -> int:
        """Number of low-risk GPTs."""
        return sum(1 for c in self.classifications if c.risk_level == RiskLevel.LOW)

    @property
    def risk_summary(self) -> dict[str, int]:
        """Summary of risk levels."""
        return {
            "high": self.high_risk_count,
            "medium": self.medium_risk_count,
            "low": self.low_risk_count,
            "total": self.total_count,
        }


class RiskClassificationError(BaseModel):
    """Error that occurred during risk classification."""

    gpt_id: str = Field(description="GPT identifier where error occurred")
    gpt_name: str = Field(description="GPT name")
    error_message: str = Field(description="Error description")
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# Models for Instructor (LLM response parsing)
class RiskClassificationResponse(BaseModel):
    """Single GPT classification from LLM response."""

    gpt_name: str = Field(description="Name of the GPT")
    file_names: list[str] = Field(description="List of associated file names")
    risk_level: Literal["High", "Medium", "Low"] = Field(description="Risk classification level")
    reasoning: str = Field(description="Explanation for the risk classification")


class BatchRiskResponse(BaseModel):
    """Batch of classifications from LLM response."""

    classifications: list[RiskClassificationResponse] = Field(description="List of GPT risk classifications")
