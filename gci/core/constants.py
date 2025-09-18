"""
Constants and configuration values for GPTs Compliance Insights.
"""

from enum import IntEnum, StrEnum

# API Base URL
API_BASE_URL = "https://api.chatgpt.com/v1"

# Version
DEFAULT_VERSION = "1.0"
PACKAGE_VERSION = "0.1.0"


class APIConstants(IntEnum):
    """API-related limits and constants."""

    DEFAULT_PAGE_SIZE = 10
    MAX_PAGE_SIZE = 100
    VALIDATION_PAGE_LIMIT = 1
    REQUEST_TIMEOUT = 30
    MAX_RETRIES = 3
    BACKOFF_MAX_TRIES = 5
    BACKOFF_FACTOR = 2
    BACKOFF_MAX_VALUE = 30


class DisplayConstants(IntEnum):
    """Display and formatting limits."""

    MAX_NAME_LENGTH = 30
    MAX_DESCRIPTION_LENGTH = 100
    API_KEY_MASK_MIN_LENGTH = 12
    API_KEY_PREFIX_LENGTH = 8
    API_KEY_SUFFIX_LENGTH = 4

    # Preview lengths
    INSTRUCTIONS_PREVIEW_LENGTH = 100
    GENERAL_PREVIEW_LENGTH = 200
    TUI_PREVIEW_MAX_LENGTH = 120

    # ID display
    ID_LENGTH_THRESHOLD = 8
    ID_PREFIX_LENGTH = 5
    ID_SUFFIX_LENGTH = 3

    # List display limits
    MAX_USERS_TO_SHOW = 10
    MAX_ENDPOINTS_TO_SHOW = 5
    MAX_LIST_ITEMS_BEFORE_MORE = 2
    MAX_TOOLS_TO_SHOW = 5
    MAX_FILES_TO_SHOW = 5
    MAX_STARTERS_TO_SHOW = 5


class TableColumnWidths(IntEnum):
    """Table column width constants for CLI display."""

    ID = 38
    NAME = 25
    DESCRIPTION = 30
    OWNER = 25
    CREATED = 12
    INSTRUCTIONS = 35
    CATEGORIES = 12
    SHARING = 12
    SHARED_WITH = 20
    STARTERS = 25
    TOOLS = 25
    FILES = 25


class FormattingConstants(IntEnum):
    """Formatting constants."""

    JSON_INDENT = 2


class RiskScoreCategories(StrEnum):
    """Risk score category names."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class TUIConstants(IntEnum):
    """TUI-specific constants."""

    MIN_SEARCH_LENGTH = 3
    MAX_SEARCH_RESULTS = 50
    MAX_MATCH_HIGHLIGHTS = 5
    PREVIEW_MAX_LENGTH = 120


class ProgressBarConstants(IntEnum):
    """Progress bar update intervals."""

    MIN_UPDATE_INTERVAL = 100  # milliseconds
    MAX_UPDATE_INTERVAL = 300  # milliseconds


class CacheLimits(IntEnum):
    """Cache-related limits."""

    MAX_CACHE_AGE_HOURS = 24
    MAX_CHECKPOINT_SIZE_MB = 100


class RiskScoreConstants(IntEnum):
    """Risk score values and thresholds."""

    # File-based risk scores
    SUSPICIOUS_FILES_SCORE = 30

    # Sharing risk scores
    HIGH_SHARING_SCORE = 20
    MODERATE_SHARING_SCORE = 10

    # Sharing user count thresholds
    HIGH_SHARING_THRESHOLD = 10
    MODERATE_SHARING_THRESHOLD = 5

    # Tool risk scores
    WEB_BROWSING_SCORE = 15
    CODE_EXECUTION_SCORE = 15
    CUSTOM_ACTIONS_SCORE = 25

    # Public sharing score
    PUBLIC_SHARING_SCORE = 20

    # Risk level thresholds
    HIGH_RISK_THRESHOLD = 70
    MEDIUM_RISK_THRESHOLD = 40


class ModelDefaults(StrEnum):
    """Default model values."""

    DEFAULT_MODEL = "gpt-4"
    DEFAULT_VERSION = "1.0"
