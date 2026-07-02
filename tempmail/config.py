"""
Configuration module for the TempMail library.

Provides a Pydantic-based configuration model that centralizes all
tunable parameters in one place.
"""

from pydantic import BaseModel, Field, HttpUrl

from tempmail.constants import (
    BASE_URL,
    DEFAULT_DOMAINS_LIMIT,
    DEFAULT_TIMEOUT,
    RETRY_BASE_DELAY,
    RETRY_EXPONENTIAL_BASE,
    RETRY_MAX_ATTEMPTS,
)


class TempMailConfig(BaseModel):
    """Runtime configuration for the TempMail client.

    All values have sensible defaults; override only what you need.

    Attributes:
        base_url: Root URL of the CleanTempMail API.
        timeout: HTTP request timeout in seconds.
        retry_max_attempts: Maximum number of retry attempts on failure.
        retry_base_delay: Initial delay (seconds) between retries.
        retry_exponential_base: Multiplier applied each retry iteration.
        default_domains_limit: Default number of domains to fetch.
        verify_ssl: Whether to verify SSL certificates.
    """

    base_url: str = Field(default=BASE_URL, description="Root URL of the API")
    timeout: int = Field(
        default=DEFAULT_TIMEOUT, ge=1, description="HTTP timeout in seconds"
    )
    retry_max_attempts: int = Field(
        default=RETRY_MAX_ATTEMPTS,
        ge=0,
        description="Max retry attempts on transient errors",
    )
    retry_base_delay: float = Field(
        default=RETRY_BASE_DELAY, ge=0.0, description="Initial retry delay in seconds"
    )
    retry_exponential_base: int = Field(
        default=RETRY_EXPONENTIAL_BASE,
        ge=2,
        description="Exponential backoff multiplier",
    )
    default_domains_limit: int = Field(
        default=DEFAULT_DOMAINS_LIMIT,
        ge=1,
        description="Default number of domains to retrieve",
    )
    verify_ssl: bool = Field(default=True, description="Verify SSL certificates")

    model_config = {"frozen": True}


# Default singleton configuration
default_config = TempMailConfig()
