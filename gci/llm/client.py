"""LLM client using Instructor with LiteLLM for structured outputs."""

import logging
from typing import Any, TypeVar, cast

import instructor
from litellm import completion
from pydantic import BaseModel

from gci.config import Config

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Base exception for LLM-related errors."""


class LLMClient:
    """LLM client using Instructor for structured outputs."""

    def __init__(
        self,
        provider: str | None = None,
        model: str | None = None,
        api_key: str | None = None,
        temperature: float | None = None,
        config: Config | None = None,
    ) -> None:
        """Initialize LLM client with Instructor.

        Args:
            provider: LLM provider (openai, anthropic, bedrock, etc.)
            model: Model name (gpt-4-turbo, claude-3-sonnet, etc.)
            api_key: API key for the provider
            temperature: Temperature for responses
            config: Application config (falls back to defaults)
        """
        self.config = config or Config()

        # Use provided values or fall back to config/defaults
        self.provider = provider or self.config.llm_provider
        self.model = model or self.config.llm_model
        self.temperature = temperature if temperature is not None else self.config.llm_temperature

        # Set API key if provided
        self.api_key = api_key
        if not self.api_key and self.config.llm_api_key:
            self.api_key = self.config.llm_api_key.get_secret_value()

        # Format model string for LiteLLM
        if self.provider == "bedrock":
            self.model_string = f"bedrock/{self.model}"
        elif self.provider == "anthropic":
            self.model_string = f"anthropic/{self.model}"
        else:
            # OpenAI and others don't need prefix
            self.model_string = self.model

        # Create Instructor client wrapping LiteLLM
        self.client = instructor.from_litellm(completion)

        logger.info(f"Initialized LLM client: provider={self.provider}, model={self.model}")

    def complete(self, messages: list[dict[str, str]], response_model: type[T]) -> T:
        """Get structured completion using Instructor.

        Args:
            messages: List of message dicts with 'role' and 'content'
            response_model: Pydantic model class for structured response

        Returns:
            Instance of response_model with validated data

        Raises:
            LLMError: If completion fails
        """
        try:
            logger.debug(f"Calling LLM completion: model={self.model_string}, response_model={response_model.__name__}")

            # Get structured response using explicit parameters
            # Cast messages to suppress type warnings - instructor handles various message formats
            messages_param = cast(Any, messages)

            if self.api_key:
                response = self.client.chat.completions.create(
                    model=self.model_string,
                    messages=messages_param,
                    temperature=self.temperature,
                    response_model=response_model,
                    api_key=self.api_key,
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model_string,
                    messages=messages_param,
                    temperature=self.temperature,
                    response_model=response_model,
                )

            logger.debug(f"LLM completion successful: {response_model.__name__}")
            return response

        except Exception as e:
            logger.error(f"LLM completion error: {e}")
            raise LLMError(f"LLM completion failed: {e}") from e

    def validate(self) -> bool:
        """Validate LLM connection with a simple test query.

        Returns:
            True if validation successful

        Raises:
            LLMError: If validation fails
        """

        class TestResponse(BaseModel):
            message: str

        try:
            response = self.complete([{"role": "user", "content": "Reply with just the word OK"}], TestResponse)
            if "OK" not in response.message.upper():
                raise LLMError(f"Validation failed: unexpected response '{response.message}'")
            return True
        except Exception as e:
            raise LLMError(f"Validation failed: {e}") from e

    def __str__(self) -> str:
        """String representation of the client."""
        return f"LLMClient(provider={self.provider}, model={self.model})"
