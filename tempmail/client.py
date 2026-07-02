"""
Core HTTP client for the TempMail library.

Handles:
- Session management with persistent default headers
- Retry logic (via ``utils.with_retry``)
- Response parsing and error mapping
- All public API operations
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from requests import Response, Session

from tempmail.config import TempMailConfig, default_config
from tempmail.constants import (
    DEFAULT_HEADERS,
    ENDPOINT_DOMAINS,
    ENDPOINT_EMAIL,
    ENDPOINT_EVENTS,
    ENDPOINT_GENERATE_EMAIL,
    ENDPOINT_INBOX,
    LOGGER_NAME,
)
from tempmail.exceptions import (
    APIError,
    EmailNotFound,
    RateLimitError,
    ConnectionError,
    ParsingError,
)
from tempmail.models import EmailAddress, EmailMessage
from tempmail.utils import build_url, with_retry

logger = logging.getLogger(LOGGER_NAME)


class TempMailClient:
    """Synchronous client for the CleanTempMail API.

    All public methods automatically retry on transient failures using an
    exponential back-off strategy as defined in :class:`~tempmail.config.TempMailConfig`.

    Args:
        config: Optional runtime configuration.  Defaults to
            :data:`~tempmail.config.default_config`.

    Example::

        from tempmail import TempMailClient

        client = TempMailClient()
        email = client.generate_email()
        print(email.address)
    """

    def __init__(self, config: Optional[TempMailConfig] = None) -> None:
        self._config = config or default_config
        self._session = self._build_session()

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def _build_session(self) -> Session:
        """Create and configure a :class:`requests.Session`.

        Returns:
            Configured session with default headers.
        """
        session = Session()
        session.headers.update(DEFAULT_HEADERS)
        return session

    def close(self) -> None:
        """Close the underlying HTTP session.

        It is safe to call this method multiple times.
        """
        self._session.close()
        logger.debug("HTTP session closed")

    def __enter__(self) -> "TempMailClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _url(self, endpoint: str) -> str:
        """Build a full URL from an endpoint path.

        Args:
            endpoint: API path starting with ``/``.

        Returns:
            Fully-qualified URL.
        """
        return build_url(self._config.base_url, endpoint)

    def _handle_response(self, response: Response, email_id: str = "") -> dict[str, Any]:
        """Validate an HTTP response and return the parsed JSON body.

        Args:
            response: The response object from ``requests``.
            email_id: Optional email ID used in :class:`~tempmail.exceptions.EmailNotFound`.

        Returns:
            Parsed JSON body as a dictionary.

        Raises:
            EmailNotFound: If the server returns HTTP 404.
            RateLimitError: If the server returns HTTP 429.
            APIError: For all other non-2xx responses.
            ParsingError: If the body is not valid JSON.
        """
        logger.debug(
            "Response: %s %s -> %d", response.request.method, response.url, response.status_code
        )

        if response.status_code == 404:
            raise EmailNotFound(email_id or "unknown")

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                "Rate limit exceeded",
                retry_after=float(retry_after) if retry_after else None,
            )

        if not response.ok:
            try:
                body = response.json()
                message = body.get("message") or body.get("error") or response.text[:300]
            except Exception:
                message = response.text[:300]
            raise APIError(
                f"API returned {response.status_code}: {message}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except Exception as exc:
            raise ParsingError(
                f"Failed to parse JSON response: {exc}", raw=response.text[:500]
            ) from exc

    def _get(self, endpoint: str, params: Optional[dict[str, Any]] = None, email_id: str = "") -> dict[str, Any]:
        """Perform a GET request with error handling.

        Args:
            endpoint: API path (e.g. ``/api/emails``).
            params: Optional query string parameters.
            email_id: Email ID for 404 error messages.

        Returns:
            Parsed JSON body.
        """
        url = self._url(endpoint)
        logger.debug("GET %s params=%s", url, params)
        try:
            response = self._session.get(
                url,
                params=params,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
            )
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(f"Connection failed: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ConnectionError(f"Request timed out: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"Request error: {exc}") from exc
        return self._handle_response(response, email_id=email_id)

    def _post(self, endpoint: str, json: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """Perform a POST request with error handling.

        Args:
            endpoint: API path.
            json: Optional JSON body.

        Returns:
            Parsed JSON body.
        """
        url = self._url(endpoint)
        logger.debug("POST %s body=%s", url, json)
        try:
            response = self._session.post(
                url,
                json=json or {},
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
            )
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(f"Connection failed: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ConnectionError(f"Request timed out: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"Request error: {exc}") from exc
        return self._handle_response(response)

    def _delete(self, endpoint: str, email_id: str = "") -> dict[str, Any]:
        """Perform a DELETE request with error handling.

        Args:
            endpoint: API path.
            email_id: Email ID for 404 error messages.

        Returns:
            Parsed JSON body.
        """
        url = self._url(endpoint)
        logger.debug("DELETE %s", url)
        try:
            response = self._session.delete(
                url,
                timeout=self._config.timeout,
                verify=self._config.verify_ssl,
            )
        except requests.exceptions.ConnectionError as exc:
            raise ConnectionError(f"Connection failed: {exc}") from exc
        except requests.exceptions.Timeout as exc:
            raise ConnectionError(f"Request timed out: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise ConnectionError(f"Request error: {exc}") from exc
        return self._handle_response(response, email_id=email_id)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_email(self) -> EmailAddress:
        """Generate a new random temporary email address.

        Makes a POST request to ``/api/generate-email`` and returns a
        parsed :class:`~tempmail.models.EmailAddress`.

        Returns:
            A newly generated :class:`~tempmail.models.EmailAddress`.

        Raises:
            APIError: If the API returns a non-successful response.
            ConnectionError: If a network-level error occurs.
            ParsingError: If the response cannot be parsed.

        Example::

            email = client.generate_email()
            print(email.address)   # e.g. "user123@example.com"
        """
        @with_retry(
            max_attempts=self._config.retry_max_attempts,
            base_delay=self._config.retry_base_delay,
            exponential_base=self._config.retry_exponential_base,
        )
        def _call() -> EmailAddress:
            body = self._post(ENDPOINT_GENERATE_EMAIL)
            # Actual response: {"success": true, "data": {"email": "..."}}
            data = body.get("data", body)
            raw_address = data.get("email") or data.get("address")
            if not raw_address:
                raise ParsingError(
                    "Could not find email address in response", raw=str(body)[:200]
                )
            email_address = EmailAddress.from_address(raw_address)
            logger.info("Generated email: %s", email_address.address)
            return email_address

        return _call()

    def get_domains(self, limit: Optional[int] = None) -> list[str]:
        """Retrieve a list of available email domains.

        Args:
            limit: Maximum number of domains to return.  Defaults to
                :attr:`~tempmail.config.TempMailConfig.default_domains_limit`.

        Returns:
            List of domain name strings.

        Raises:
            APIError: On non-successful response.
            ConnectionError: On network error.

        Example::

            domains = client.get_domains(limit=10)
        """
        effective_limit = limit if limit is not None else self._config.default_domains_limit

        @with_retry(
            max_attempts=self._config.retry_max_attempts,
            base_delay=self._config.retry_base_delay,
            exponential_base=self._config.retry_exponential_base,
        )
        def _call() -> list[str]:
            body = self._get(ENDPOINT_DOMAINS, params={"limit": effective_limit})
            # Actual response: {"success": true, "data": {"domains": [...], "total": N}}
            data = body.get("data", body)
            domains = data.get("domains", [])
            if not isinstance(domains, list):
                raise ParsingError(
                    "Unexpected domains format in response", raw=str(body)[:200]
                )
            logger.info(
                "Retrieved %d domains (total available: %s)",
                len(domains),
                data.get("total", "?"),
            )
            return domains

        return _call()

    def get_messages(self, email: str) -> list[EmailMessage]:
        """Fetch all messages in the inbox for *email*.

        Args:
            email: The full temporary email address to check.

        Returns:
            List of :class:`~tempmail.models.EmailMessage` objects, possibly empty.

        Raises:
            APIError: On non-successful response.
            ConnectionError: On network error.

        Example::

            messages = client.get_messages("user@example.com")
            for msg in messages:
                print(msg.subject)
        """
        @with_retry(
            max_attempts=self._config.retry_max_attempts,
            base_delay=self._config.retry_base_delay,
            exponential_base=self._config.retry_exponential_base,
        )
        def _call() -> list[EmailMessage]:
            body = self._get(ENDPOINT_INBOX, params={"email": email})
            # Actual response: {"success": true, "data": {"emails": [...], "count": N}}
            data = body.get("data", body)
            raw_emails = data.get("emails", [])
            if not isinstance(raw_emails, list):
                raise ParsingError(
                    "Unexpected emails format in response", raw=str(body)[:200]
                )
            messages = []
            for item in raw_emails:
                try:
                    # API returns "from_address" but EmailMessage uses alias "from"
                    if "from_address" in item and "from" not in item:
                        item["from"] = item["from_address"]
                    # API returns "html_content" but model uses "html"
                    if "html_content" in item and "html" not in item:
                        item["html"] = item["html_content"]
                    # API returns "content" but model uses "text"
                    if "content" in item and "text" not in item:
                        item["text"] = item["content"]
                    # API returns "timestamp" but model uses "date"
                    if "timestamp" in item and "date" not in item:
                        item["date"] = item["timestamp"]
                    item["raw"] = item.copy()
                    messages.append(EmailMessage(**item))
                except Exception as exc:
                    logger.warning("Could not parse email item: %s", exc)
            logger.info(
                "Inbox for %s: %d message(s)", email, len(messages)
            )
            return messages

        return _call()

    def read_message(self, message_id: str) -> EmailMessage:
        """Read a single email message by its ID.

        Args:
            message_id: Unique identifier of the message.

        Returns:
            The corresponding :class:`~tempmail.models.EmailMessage`.

        Raises:
            EmailNotFound: If *message_id* does not exist.
            APIError: On non-successful response.
            ConnectionError: On network error.

        Example::

            msg = client.read_message("abc123")
            print(msg.html)
        """
        @with_retry(
            max_attempts=self._config.retry_max_attempts,
            base_delay=self._config.retry_base_delay,
            exponential_base=self._config.retry_exponential_base,
        )
        def _call() -> EmailMessage:
            endpoint = f"{ENDPOINT_EMAIL}/{message_id}"
            body = self._get(endpoint, email_id=message_id)
            data = body.get("data", body)
            if not data:
                raise ParsingError(
                    f"Empty data in read_message response for ID={message_id!r}"
                )
            # Normalise: some APIs nest the message under 'email' key
            if "email" in data and isinstance(data["email"], dict):
                data = data["email"]
                
            # Field mapping (API to Model alias)
            if "from_address" in data and "from" not in data:
                data["from"] = data["from_address"]
            if "html_content" in data and "html" not in data:
                data["html"] = data["html_content"]
            if "content" in data and "text" not in data:
                data["text"] = data["content"]
            if "timestamp" in data and "date" not in data:
                data["date"] = data["timestamp"]
                
            data["raw"] = data.copy()
            message = EmailMessage(**data)
            logger.info("Read message ID=%s subject=%r", message_id, message.subject)
            return message

        return _call()

    def delete_message(self, message_id: str) -> bool:
        """Delete a single email message.

        Args:
            message_id: Unique identifier of the message to delete.

        Returns:
            ``True`` if deletion was successful.

        Raises:
            EmailNotFound: If *message_id* does not exist.
            APIError: On non-successful response.
            ConnectionError: On network error.

        Example::

            success = client.delete_message("abc123")
        """
        @with_retry(
            max_attempts=self._config.retry_max_attempts,
            base_delay=self._config.retry_base_delay,
            exponential_base=self._config.retry_exponential_base,
        )
        def _call() -> bool:
            endpoint = f"{ENDPOINT_EMAIL}/{message_id}"
            body = self._delete(endpoint, email_id=message_id)
            success: bool = bool(body.get("success", True))
            logger.info("Deleted message ID=%s success=%s", message_id, success)
            return success

        return _call()

    def monitor(
        self,
        email: str,
        callback: Optional[Any] = None,
        timeout: Optional[int] = None,
    ) -> Any:
        """Monitor an inbox for new messages using Server-Sent Events.

        When *callback* is ``None``, this method returns a **generator** that
        yields :class:`~tempmail.models.EmailMessage` objects as they arrive.
        The generator blocks until the connection drops or an error occurs.

        When *callback* is provided, it is called with each new
        :class:`~tempmail.models.EmailMessage` and this method blocks until
        the SSE stream ends.

        For async usage, see :func:`~tempmail.monitor.monitor_async`.

        Args:
            email: The temporary email address to watch.
            callback: Optional callable ``(message: EmailMessage) -> None``.
            timeout: Override the session timeout for this streaming request.

        Yields:
            :class:`~tempmail.models.EmailMessage` — one per incoming event
            (only when *callback* is ``None``).

        Example (blocking iterator)::

            for msg in client.monitor("user@example.com"):
                print(msg.subject)

        Example (callback)::

            def on_email(msg):
                print(msg.subject)

            client.monitor("user@example.com", callback=on_email)
        """
        from tempmail.monitor import _stream_sse

        stream = _stream_sse(
            session=self._session,
            url=self._url(ENDPOINT_EVENTS),
            email=email,
            config=self._config,
            timeout=timeout,
        )

        if callback is not None:
            for message in stream:
                callback(message)
        else:
            return stream
