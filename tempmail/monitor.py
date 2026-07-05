"""
Monitor module — real-time inbox monitoring via Server-Sent Events (SSE).

Provides:
- A blocking generator-based stream via ``_stream_sse``
- An async wrapper via ``monitor_async``
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from collections.abc import AsyncIterator, Iterator
from typing import Any, Callable, Optional

import requests
from requests import Session

from tempmail.config import TempMailConfig
from tempmail.constants import (
    LOGGER_NAME,
    SSE_EVENT_CONNECTED,
    SSE_EVENT_NEW_EMAIL,
    SSE_EVENT_PING,
)
from tempmail.exceptions import ConnectionError, ParsingError
from tempmail.models import EmailMessage

logger = logging.getLogger(LOGGER_NAME)


# ---------------------------------------------------------------------------
# SSE line parser (minimal, no external dependency)
# ---------------------------------------------------------------------------


def _parse_sse_line(line: str) -> tuple[str, str]:
    """Parse a single SSE line into ``(field, value)`` tuple.

    Args:
        line: Raw SSE line (without trailing ``\\n``).

    Returns:
        Tuple of ``(field_name, field_value)``.
        Field name may be empty if the line is a comment or blank.
    """
    if line.startswith(":"):
        return "comment", line[1:].strip()
    if ":" in line:
        field, _, value = line.partition(":")
        return field.strip(), value.lstrip(" ")
    return line.strip(), ""


def _parse_sse_chunk(chunk: str) -> list[dict[str, str]]:
    """Parse a multi-line SSE chunk into a list of event dicts.

    Each event dict may contain keys: ``event``, ``data``, ``id``, ``retry``.

    Args:
        chunk: Raw SSE message block (may include multiple ``\\n``-separated fields).

    Returns:
        List of parsed event dicts, one per logical SSE event.
    """
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}

    for raw_line in chunk.splitlines():
        line = raw_line.rstrip("\r")
        if not line:
            # Blank line = dispatch event
            if current:
                events.append(current)
                current = {}
            continue
        field, value = _parse_sse_line(line)
        if field in ("data", "event", "id", "retry"):
            # Concatenate multi-line data fields
            if field == "data" and "data" in current:
                current["data"] = current["data"] + "\n" + value
            else:
                current[field] = value

    if current:
        events.append(current)

    return events


# ---------------------------------------------------------------------------
# Email message deserializer for SSE payloads
# ---------------------------------------------------------------------------


def _deserialize_event(raw_data: str) -> Optional[EmailMessage]:
    """Attempt to turn raw SSE data into an :class:`~tempmail.models.EmailMessage`.

    Args:
        raw_data: The ``data:`` value from the SSE event.

    Returns:
        Parsed :class:`~tempmail.models.EmailMessage`, or ``None`` if the
        payload should be skipped (e.g. a heartbeat or unknown format).
    """
    raw_data = raw_data.strip()
    if not raw_data or raw_data in ("connected", "ping", "{}"):
        return None
    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError:
        logger.debug("SSE: non-JSON data skipped: %r", raw_data[:100])
        return None

    # Handle wrapped payloads: {"data": {...}} or {"email": {...}}
    if isinstance(payload, dict):
        if "data" in payload and isinstance(payload["data"], dict):
            payload = payload["data"]
        if "email" in payload and isinstance(payload["email"], dict):
            payload = payload["email"]

    if not isinstance(payload, dict):
        logger.debug("SSE: payload not a dict: %r", str(payload)[:100])
        return None
        
    # Map 'email_id' to 'id' for SSE events
    if "email_id" in payload and "id" not in payload:
        payload["id"] = payload["email_id"]
        
    if "id" not in payload:
        logger.debug("SSE: payload without 'id' skipped: %r", str(payload)[:100])
        return None

    try:
        if "from_address" in payload and "from" not in payload:
            payload["from"] = payload["from_address"]
        if "html_content" in payload and "html" not in payload:
            payload["html"] = payload["html_content"]
        if "content" in payload and "text" not in payload:
            payload["text"] = payload["content"]
        if "timestamp" in payload and "date" not in payload:
            payload["date"] = payload["timestamp"]
            
        payload["raw"] = payload.copy()
        return EmailMessage(**payload)
    except Exception as exc:
        logger.warning("SSE: failed to parse email payload: %s — %s", exc, payload)
        return None


# ---------------------------------------------------------------------------
# Blocking SSE stream
# ---------------------------------------------------------------------------


def _stream_sse(
    session: Session,
    url: str,
    email: str,
    config: TempMailConfig,
    timeout: Optional[int] = None,
    cancel_event: Optional[threading.Event] = None,
) -> Iterator[EmailMessage]:
    """Stream SSE events from the API and yield :class:`~tempmail.models.EmailMessage`.

    This is a blocking generator.  It reconnects automatically if the
    stream drops due to a transient network issue, up to
    :attr:`~tempmail.config.TempMailConfig.retry_max_attempts` times.

    Args:
        session: The authenticated :class:`requests.Session`.
        url: Full SSE stream URL.
        email: Email address to monitor.
        config: Runtime configuration.
        timeout: Optional per-stream timeout override (seconds).

    Yields:
        :class:`~tempmail.models.EmailMessage` for each new email event.

    Raises:
        ConnectionError: If all reconnect attempts fail.
    """
    # SSE needs persistent connection - timeout should be None or very large
    # We use (connect_timeout, None) to set only the connection timeout
    effective_timeout = (10, None)  # 10s connect timeout, no read timeout
    params = {"email": email}

    logger.info("Starting SSE monitor for %s at %s", email, url)

    attempts = 0
    # SSE: reconnect indefinitely (no max_attempts for persistent monitoring)
    max_attempts = 999999

    while True:
        if cancel_event and cancel_event.is_set():
            logger.info("SSE: stream %s cancelled before connecting", email)
            return

        try:
            with session.get(
                url,
                params=params,
                stream=True,
                timeout=effective_timeout,
                verify=config.verify_ssl,
            ) as response:
                if not response.ok:
                    raise ConnectionError(
                        f"SSE stream returned HTTP {response.status_code}"
                    )
                attempts = 0  # reset on successful connection
                logger.debug("SSE stream connected for %s", email)

                buffer = ""
                for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
                    if cancel_event and cancel_event.is_set():
                        logger.info("SSE: stream %s cancelled during read", email)
                        return

                    if chunk is None:
                        continue
                    buffer += chunk

                    # Process complete SSE events (separated by double newline)
                    while "\n\n" in buffer or "\r\n\r\n" in buffer:
                        if "\r\n\r\n" in buffer:
                            event_block, _, buffer = buffer.partition("\r\n\r\n")
                        else:
                            event_block, _, buffer = buffer.partition("\n\n")

                        for event in _parse_sse_chunk(event_block):
                            event_type = event.get("event", "")
                            raw_data = event.get("data", "")

                            # Skip explicit heartbeat/control events only
                            if event_type in (SSE_EVENT_PING, SSE_EVENT_CONNECTED):
                                logger.debug("SSE: %s event", event_type)
                                continue

                            # Skip empty events (no data at all)
                            if not raw_data:
                                continue

                            # Process: explicit new_email event OR any event with data
                            logger.debug("SSE: event_type=%r data=%r", event_type, raw_data[:80])
                            message = _deserialize_event(raw_data)
                            if message:
                                logger.info(
                                    "SSE: new email received id=%s subject=%r", message.id, message.subject
                                )
                                yield message

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            attempts += 1
            if attempts > max_attempts:
                raise ConnectionError(
                    f"SSE stream disconnected after {max_attempts} reconnect attempts: {exc}"
                ) from exc
            import time
            delay = config.retry_base_delay * (config.retry_exponential_base ** (attempts - 1))
            logger.warning(
                "SSE: connection lost (attempt %d/%d). Reconnecting in %.1fs: %s",
                attempts,
                max_attempts,
                delay,
                exc,
            )
            time.sleep(delay)
        except StopIteration:
            # Caller closed the generator
            logger.info("SSE: monitoring stopped by caller")
            return
        except GeneratorExit:
            logger.info("SSE: generator closed")
            return


# ---------------------------------------------------------------------------
# Async wrapper
# ---------------------------------------------------------------------------


async def monitor_async(
    email: str,
    callback: Callable[[EmailMessage], Any],
    config: Optional[TempMailConfig] = None,
    timeout: Optional[int] = None,
) -> None:
    """Async wrapper around the blocking SSE monitor.

    Runs the SSE stream in a thread pool executor so the event loop is not
    blocked. ``callback`` is called in the event loop thread via
    ``asyncio.run_coroutine_threadsafe`` when it is a coroutine, or directly
    when it is a plain callable.

    Args:
        email: Temporary email address to monitor.
        callback: Async or sync callable invoked for each new message.
        config: Optional runtime configuration.
        timeout: Optional per-stream timeout override (seconds).

    Example::

        import asyncio
        from tempmail import monitor_async

        async def handler(msg):
            print(msg.subject)

        asyncio.run(monitor_async("user@example.com", handler))
    """
    from tempmail.client import TempMailClient
    from tempmail.config import default_config

    effective_config = config or default_config
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue[Optional[EmailMessage]] = asyncio.Queue()
    cancel_event = threading.Event()

    def _producer() -> None:
        """Run the blocking SSE stream and enqueue messages."""
        with TempMailClient(effective_config) as client:
            try:
                for message in client.monitor(email, timeout=timeout, cancel_event=cancel_event):
                    asyncio.run_coroutine_threadsafe(
                        queue.put(message), loop
                    ).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(None), loop).result()

    # Run producer in a thread
    producer_future = loop.run_in_executor(None, _producer)

    try:
        while True:
            message = await queue.get()
            if message is None:
                break
            if asyncio.iscoroutinefunction(callback):
                await callback(message)
            else:
                callback(message)

        await producer_future
    except asyncio.CancelledError:
        logger.info("SSE: Async task cancelled for %s. Setting event to gracefully stop thread...", email)
        cancel_event.set()
        raise
