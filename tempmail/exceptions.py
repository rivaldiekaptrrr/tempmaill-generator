"""
Custom exception hierarchy for the TempMail library.

All exceptions are derived from ``TempMailException`` so callers can
catch either a specific error or the entire TempMail exception family
with a single ``except TempMailException`` clause.
"""

from __future__ import annotations


class TempMailException(Exception):
    """Base exception for all TempMail library errors.

    Attributes:
        message: Human-readable description of the error.
        status_code: HTTP status code, if applicable.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code

    def __repr__(self) -> str:  # pragma: no cover
        return f"{self.__class__.__name__}(message={self.message!r}, status_code={self.status_code!r})"


class APIError(TempMailException):
    """Raised when the API returns a non-successful response.

    This covers HTTP 4xx/5xx responses that are not more specifically
    classified by another exception subclass.
    """


class RateLimitError(TempMailException):
    """Raised when the API rate-limits the client (HTTP 429).

    Attributes:
        retry_after: Seconds to wait before retrying, if provided by the server.
    """

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class EmailNotFound(TempMailException):
    """Raised when the requested email ID does not exist (HTTP 404)."""

    def __init__(self, email_id: str) -> None:
        super().__init__(
            f"Email with ID '{email_id}' was not found.", status_code=404
        )
        self.email_id = email_id


class ConnectionError(TempMailException):
    """Raised when a network-level error occurs (e.g. DNS failure, timeout).

    This is distinct from :class:`APIError` which requires a completed HTTP
    response.
    """


class ParsingError(TempMailException):
    """Raised when the library fails to parse an API response or email body.

    Attributes:
        raw: The raw content that could not be parsed.
    """

    def __init__(self, message: str, raw: str | None = None) -> None:
        super().__init__(message)
        self.raw = raw
