"""
Pydantic models for the TempMail library.

All models are strict-by-default and immutable once created.
Extra fields returned by the API are ignored so the models remain
forward-compatible as the API evolves.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator


class _BaseModel(BaseModel):
    """Shared Pydantic configuration for all TempMail models."""

    model_config = {
        "frozen": True,
        "extra": "ignore",
        "populate_by_name": True,
    }


class EmailAddress(_BaseModel):
    """A freshly generated temporary email address.

    Attributes:
        address: Full email address (e.g. ``user@domain.com``).
        username: Local part before the ``@`` symbol.
        domain: Domain part after the ``@`` symbol.
        created_at: Timestamp when the address was generated.
    """

    address: str = Field(..., description="Full email address")
    username: str = Field(..., description="Local part of the address")
    domain: str = Field(..., description="Domain part of the address")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when the address was generated",
    )

    @classmethod
    def from_address(cls, address: str) -> "EmailAddress":
        """Construct an :class:`EmailAddress` from a plain email string.

        Args:
            address: Full email address string.

        Returns:
            A populated :class:`EmailAddress` instance.

        Raises:
            ValueError: If *address* does not contain exactly one ``@``.
        """
        parts = address.split("@")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError(f"Invalid email address: {address!r}")
        return cls(address=address, username=parts[0], domain=parts[1])

    def __str__(self) -> str:
        return self.address


class Attachment(_BaseModel):
    """A file attachment associated with an email message.

    Attributes:
        filename: Name of the attached file.
        content_type: MIME type (e.g. ``application/pdf``).
        size: Size in bytes.
        content: Raw Base64-encoded content, if available.
    """

    filename: str = Field(..., description="Attachment filename")
    content_type: str = Field("application/octet-stream", description="MIME type")
    size: int = Field(0, ge=0, description="File size in bytes")
    content: str | None = Field(None, description="Base64-encoded content")


class EmailMessage(_BaseModel):
    """A received email message.

    Attributes:
        id: Unique message identifier used for read/delete operations.
        sender: Sender address (maps to the ``from`` field in the API).
        to: Recipient address.
        subject: Email subject line.
        text: Plain-text body.
        html: HTML body.
        date: When the message was received.
        attachments: List of file attachments.
        raw: The full raw API payload for inspection / forward-compatibility.
    """

    id: str = Field(..., description="Unique message ID")
    sender: str = Field(..., alias="from", description="Sender email address")
    to: str = Field("", description="Recipient email address")
    subject: str = Field("", description="Email subject")
    text: str = Field("", description="Plain-text body")
    html: str = Field("", description="HTML body")
    date: datetime | None = Field(None, description="Received timestamp")
    attachments: list[Attachment] = Field(
        default_factory=list, description="File attachments"
    )
    raw: dict[str, Any] = Field(
        default_factory=dict,
        description="Full raw API payload",
        exclude=True,
    )

    @field_validator("sender", mode="before")
    @classmethod
    def _coerce_sender(cls, v: Any) -> str:
        """Accept both plain strings and dicts with an ``address`` key."""
        if isinstance(v, dict):
            return v.get("address", v.get("email", str(v)))
        return str(v) if v is not None else ""

    @field_validator("to", mode="before")
    @classmethod
    def _coerce_to(cls, v: Any) -> str:
        if isinstance(v, dict):
            return v.get("address", v.get("email", str(v)))
        if isinstance(v, list) and v:
            first = v[0]
            if isinstance(first, dict):
                return first.get("address", first.get("email", str(first)))
            return str(first)
        return str(v) if v is not None else ""

    @field_validator("date", mode="before")
    @classmethod
    def _coerce_date(cls, v: Any) -> datetime | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, (int, float)):
            return datetime.fromtimestamp(v, tz=timezone.utc)
        if isinstance(v, str):
            for fmt in (
                "%Y-%m-%dT%H:%M:%S.%fZ",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%dT%H:%M:%S",
                "%a, %d %b %Y %H:%M:%S %z",
            ):
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
        return None

    def __str__(self) -> str:
        return f"EmailMessage(id={self.id!r}, subject={self.subject!r})"
