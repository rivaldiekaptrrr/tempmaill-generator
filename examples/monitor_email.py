"""
Example: Monitor an inbox for new emails in real-time.

Demonstrates three monitoring styles:
1. Blocking iterator (default)
2. Callback-based
3. Async

Usage:
    python examples/monitor_email.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys

from tempmail import TempMailClient, extract_otp, extract_verification_urls, setup_logging
from tempmail.models import EmailMessage
from tempmail.monitor import monitor_async


# ---------------------------------------------------------------------------
# Style 1: Blocking iterator
# ---------------------------------------------------------------------------


def monitor_blocking(email_address: str) -> None:
    """Monitor inbox using a blocking for-loop."""

    print(f"\n[Blocking] Monitoring: {email_address}")
    print("Press Ctrl+C to stop.\n")

    with TempMailClient() as client:
        for message in client.monitor(email_address):
            _print_message(message)
            # Stop after first message for demo purposes
            break


# ---------------------------------------------------------------------------
# Style 2: Callback-based
# ---------------------------------------------------------------------------


def _on_email_received(message: EmailMessage) -> None:
    """Callback invoked for each new email."""
    print("[Callback] New email received!")
    _print_message(message)


def monitor_with_callback(email_address: str) -> None:
    """Monitor inbox using a callback function."""

    print(f"\n[Callback] Monitoring: {email_address}")
    print("Press Ctrl+C to stop.\n")

    with TempMailClient() as client:
        client.monitor(email_address, callback=_on_email_received)


# ---------------------------------------------------------------------------
# Style 3: Async
# ---------------------------------------------------------------------------


async def _async_handler(message: EmailMessage) -> None:
    """Async callback for monitor_async."""
    print("[Async] New email received!")
    _print_message(message)


async def monitor_async_example(email_address: str) -> None:
    """Monitor inbox using asyncio."""

    print(f"\n[Async] Monitoring: {email_address}")
    print("Press Ctrl+C to stop.\n")

    await monitor_async(email_address, callback=_async_handler)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _print_message(message: EmailMessage) -> None:
    print("-" * 60)
    print(f"  ID      : {message.id}")
    print(f"  From    : {message.sender}")
    print(f"  Subject : {message.subject}")
    if message.date:
        print(f"  Date    : {message.date.strftime('%Y-%m-%d %H:%M:%S')}")

    otp = extract_otp(message.text, message.html)
    if otp:
        print(f"  OTP     : {otp}")

    links = extract_verification_urls(message.html, message.text)
    if links:
        print("  Verify  :")
        for link in links:
            print(f"    {link}")

    print("-" * 60)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    setup_logging(level=logging.INFO)

    with TempMailClient() as client:
        email = client.generate_email()

    print("=" * 60)
    print("Real-time Inbox Monitor")
    print("=" * 60)
    print(f"Email: {email.address}")
    print("\nStyle options:")
    print("  1 - Blocking iterator")
    print("  2 - Callback-based")
    print("  3 - Async (asyncio)")
    choice = input("Choose [1/2/3] (default: 1): ").strip() or "1"

    if choice == "2":
        monitor_with_callback(email.address)
    elif choice == "3":
        asyncio.run(monitor_async_example(email.address))
    else:
        monitor_blocking(email.address)


if __name__ == "__main__":
    main()
