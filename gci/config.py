"""Configuration management for GCI."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Application configuration."""

    api_key: SecretStr | None = Field(default=None, alias="GCI_OPENAI_API_KEY", description="OpenAI Compliance API key")
    workspace_id: str | None = Field(default=None, alias="GCI_OPENAI_WORKSPACE_ID", description="OpenAI workspace ID")
    output_dir: Path = Field(
        default_factory=lambda: Path.cwd() / "reports",
        alias="GCI_OUTPUT_DIR",
        description="Output directory for reports",
    )

    # LLM Configuration
    llm_provider: str = Field(
        default="openai",
        alias="GCI_LLM_PROVIDER",
        description="LLM provider (openai, anthropic, etc.)",
    )
    llm_model: str = Field(
        default="gpt-4-turbo",
        alias="GCI_LLM_MODEL",
        description="LLM model to use for analysis",
    )
    llm_api_key: SecretStr | None = Field(
        default=None,
        alias="GCI_LLM_API_KEY",
        description="LLM API key (defaults to provider's env var)",
    )
    llm_temperature: float = Field(
        default=0.1,
        alias="GCI_LLM_TEMPERATURE",
        description="LLM temperature for responses",
    )

    model_config = SettingsConfigDict(
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )


def load_config() -> Config:
    """Load configuration from environment and .env file."""
    return Config()
