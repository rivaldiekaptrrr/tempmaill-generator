"""
Utility helpers for the TempMail library.

Includes:
- Retry decorator with exponential backoff
- Logging setup helper
"""

from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar

from tempmail.constants import (
    LOGGER_NAME,
    RETRY_BASE_DELAY,
    RETRY_EXPONENTIAL_BASE,
    RETRY_MAX_ATTEMPTS,
)
from tempmail.exceptions import ConnectionError, RateLimitError, TempMailException

F = TypeVar("F", bound=Callable[..., Any])

logger = logging.getLogger(LOGGER_NAME)


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def setup_logging(
    level: int = logging.INFO,
    fmt: str = "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
) -> None:
    """Configure the TempMail library logger.

    Call this once at the entry point of your application if you want
    structured log output.  If you manage logging yourself, you do not
    need to call this helper.

    Args:
        level: Python logging level (e.g. ``logging.DEBUG``).
        fmt: Log format string.
    """
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(fmt))
    lib_logger = logging.getLogger(LOGGER_NAME)
    lib_logger.setLevel(level)
    if not lib_logger.handlers:
        lib_logger.addHandler(handler)
    lib_logger.propagate = False


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------


def with_retry(
    max_attempts: int = RETRY_MAX_ATTEMPTS,
    base_delay: float = RETRY_BASE_DELAY,
    exponential_base: int = RETRY_EXPONENTIAL_BASE,
    reraise_immediately: tuple[type[Exception], ...] = (
        RateLimitError,
    ),
) -> Callable[[F], F]:
    """Decorator that retries a function on transient errors.

    Uses exponential backoff:  ``delay = base_delay * exponential_base ** attempt``

    Args:
        max_attempts: Total number of attempts (initial + retries).
        base_delay: Initial delay in seconds before the first retry.
        exponential_base: Multiplier applied on each subsequent retry.
        reraise_immediately: Exception types that are *not* retried and are
            re-raised immediately to the caller.

    Returns:
        Decorated function.

    Example::

        @with_retry(max_attempts=3, base_delay=1.0)
        def call_api():
            ...
    """

    def decorator(func: F) -> F:  # type: ignore[return]
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except reraise_immediately as exc:
                    logger.warning(
                        "Non-retryable error in %s (attempt %d/%d): %s",
                        func.__qualname__,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    raise
                except TempMailException as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        delay = base_delay * (exponential_base ** (attempt - 1))
                        logger.warning(
                            "Transient error in %s (attempt %d/%d). "
                            "Retrying in %.1fs: %s",
                            func.__qualname__,
                            attempt,
                            max_attempts,
                            delay,
                            exc,
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            "All %d attempts failed for %s: %s",
                            max_attempts,
                            func.__qualname__,
                            exc,
                        )
                except Exception as exc:  # noqa: BLE001
                    # Wrap unexpected exceptions
                    last_exc = ConnectionError(
                        f"Unexpected error in {func.__qualname__}: {exc}"
                    )
                    if attempt < max_attempts:
                        delay = base_delay * (exponential_base ** (attempt - 1))
                        logger.warning(
                            "Unexpected error in %s (attempt %d/%d). "
                            "Retrying in %.1fs: %s",
                            func.__qualname__,
                            attempt,
                            max_attempts,
                            delay,
                            exc,
                        )
                        time.sleep(delay)
            assert last_exc is not None
            raise last_exc

        return wrapper  # type: ignore[return-value]

    return decorator


def build_url(base: str, path: str) -> str:
    """Safely join a base URL and a path segment.

    Args:
        base: Root URL without trailing slash.
        path: Path starting with ``/``.

    Returns:
        Fully-qualified URL string.
    """
    return f"{base.rstrip('/')}/{path.lstrip('/')}"
