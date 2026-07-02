"""
TempMail — Python client library for CleanTempMail.

Quick-start example::

    from tempmail import TempMailClient

    client = TempMailClient()
    email = client.generate_email()
    print(email.address)

    for msg in client.monitor(email.address):
        print(msg.subject)
"""

from __future__ import annotations

from tempmail.client import TempMailClient
from tempmail.config import TempMailConfig, default_config
from tempmail.exceptions import (
    APIError,
    ConnectionError,
    EmailNotFound,
    ParsingError,
    RateLimitError,
    TempMailException,
)
from tempmail.models import Attachment, EmailAddress, EmailMessage
from tempmail.monitor import monitor_async
from tempmail.parser import extract_links, extract_otp, extract_verification_urls
from tempmail.utils import setup_logging

__all__ = [
    # Client
    "TempMailClient",
    # Configuration
    "TempMailConfig",
    "default_config",
    # Models
    "EmailAddress",
    "EmailMessage",
    "Attachment",
    # Exceptions
    "TempMailException",
    "APIError",
    "RateLimitError",
    "EmailNotFound",
    "ConnectionError",
    "ParsingError",
    # Async monitor
    "monitor_async",
    # Parser utilities
    "extract_links",
    "extract_otp",
    "extract_verification_urls",
    # Logging
    "setup_logging",
]

__version__ = "1.0.0"
__author__ = "TempMail Contributors"
