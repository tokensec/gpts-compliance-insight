"""Custom exceptions for GPTs Compliance Insights."""

from typing import Any


class GCIError(Exception):
    """Base exception for all GCI errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize GCI error.

        Args:
            message: Error message
            details: Additional error details

        """
        super().__init__(message)
        self.details = details or {}


class ConfigurationError(GCIError):
    """Raised when configuration is invalid or missing."""


class APIError(GCIError):
    """Base class for API-related errors."""

    def __init__(
        self,
        status_code: int,
        message: str,
        response_text: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Initialize API error.

        Args:
            status_code: HTTP status code
            message: Error message
            response_text: Raw response text from API
            details: Additional error details

        """
        super().__init__(message, details)
        self.status_code = status_code
        self.response_text = response_text


class AuthenticationError(APIError):
    """Raised when authentication fails (401)."""

    def __init__(self, message: str = "Authentication failed", response_text: str | None = None) -> None:
        super().__init__(401, message, response_text)


class PermissionError(APIError):
    """Raised when access is forbidden (403)."""

    def __init__(self, message: str = "Access forbidden", response_text: str | None = None) -> None:
        super().__init__(403, message, response_text)


class NotFoundError(APIError):
    """Raised when resource is not found (404)."""

    def __init__(self, message: str = "Resource not found", response_text: str | None = None) -> None:
        super().__init__(404, message, response_text)


class RateLimitError(APIError):
    """Raised when rate limit is exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        response_text: str | None = None,
        retry_after: int | None = None,
    ) -> None:
        super().__init__(429, message, response_text)
        self.retry_after = retry_after


class ValidationError(GCIError):
    """Raised when input validation fails."""

    def __init__(self, field: str, value: Any, message: str) -> None:
        super().__init__(message, {"field": field, "value": value})
        self.field = field
        self.value = value


class CacheError(GCIError):
    """Raised when cache operations fail."""


class ExportError(GCIError):
    """Raised when export operations fail."""

    def __init__(self, format: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.format = format


class AnalysisError(GCIError):
    """Raised when AI analysis fails."""

    def __init__(self, agent_type: str, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details)
        self.agent_type = agent_type


class TimeoutError(GCIError):
    """Raised when operation times out."""

    def __init__(self, operation: str, timeout_seconds: float) -> None:
        message = f"Operation '{operation}' timed out after {timeout_seconds} seconds"
        super().__init__(message, {"operation": operation, "timeout_seconds": timeout_seconds})
        self.operation = operation
        self.timeout_seconds = timeout_seconds


class WorkspaceError(GCIError):
    """Raised when workspace operations fail."""


class GPTNotFoundError(NotFoundError):
    """Raised when a specific GPT is not found."""

    def __init__(self, gpt_id: str) -> None:
        super().__init__(f"GPT '{gpt_id}' not found")
        self.gpt_id = gpt_id


class InvalidCredentialsError(AuthenticationError):
    """Raised when API credentials are invalid."""

    def __init__(self, credential_type: str = "API key") -> None:
        super().__init__(f"Invalid {credential_type}")
        self.credential_type = credential_type


class RegexValidationError(ValidationError):
    """Raised when regex pattern validation fails."""

    def __init__(self, pattern: str, reason: str) -> None:
        super().__init__("pattern", pattern, f"Invalid regex pattern: {reason}")
        self.pattern = pattern
        self.reason = reason
