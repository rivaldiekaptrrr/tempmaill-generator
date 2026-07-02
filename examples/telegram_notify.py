"""
Example: Monitor inbox and send new email notifications to Telegram.

Flow:
    Generate email
        ↓
    Monitor inbox (SSE)
        ↓
    New email arrives → Extract verification link / OTP
        ↓
    Send notification to Telegram

Setup:
    1. Create a Telegram bot via @BotFather and get the BOT_TOKEN.
    2. Get your CHAT_ID (send a message to your bot, then call
       https://api.telegram.org/bot<TOKEN>/getUpdates)
    3. Set environment variables:
         TELEGRAM_BOT_TOKEN=<your bot token>
         TELEGRAM_CHAT_ID=<your chat id>

Usage:
    python examples/telegram_notify.py
"""

from __future__ import annotations

import logging
import os

import requests

from tempmail import TempMailClient, extract_otp, extract_verification_urls, setup_logging
from tempmail.models import EmailMessage

# ---------------------------------------------------------------------------
# Configuration from environment variables
# ---------------------------------------------------------------------------

TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "8769394239:AAE5_wd77Rn6hOYiLKsOPZ2RjtIwvSsvOps")
TELEGRAM_CHAT_ID: str = os.environ.get("TELEGRAM_CHAT_ID", "7003798101")

TELEGRAM_API_URL: str = "https://api.telegram.org/bot{token}/sendMessage"

logger = logging.getLogger("tempmail.examples.telegram")


# ---------------------------------------------------------------------------
# Telegram helper
# ---------------------------------------------------------------------------


def send_telegram_message(text: str) -> bool:
    """Send a text message to a Telegram chat.

    Args:
        text: Message body (supports Markdown).

    Returns:
        ``True`` if the message was sent successfully, ``False`` otherwise.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error(
            "TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables are required."
        )
        return False

    url = TELEGRAM_API_URL.format(token=TELEGRAM_BOT_TOKEN)
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False,
    }

    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        logger.debug("Telegram message sent successfully")
        return True
    except Exception as exc:
        logger.error("Failed to send Telegram message: %s", exc)
        return False


# ---------------------------------------------------------------------------
# Email handler
# ---------------------------------------------------------------------------


def on_new_email(message: EmailMessage) -> None:
    """Callback invoked whenever a new email arrives.

    Extracts OTP and verification URLs, then sends a Telegram notification.

    Args:
        message: The newly received email.
    """
    logger.info("New email: subject=%r from=%r", message.subject, message.sender)

    lines: list[str] = [
        "📬 *New Email Received*",
        f"*Subject:* {message.subject or '(no subject)'}",
        f"*From:* `{message.sender}`",
    ]

    if message.date:
        lines.append(f"*Date:* {message.date.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    # OTP extraction
    otp = extract_otp(message.text, message.html)
    if otp:
        lines.append(f"\n🔑 *OTP Code:* `{otp}`")

    # Verification URL extraction
    verify_links = extract_verification_urls(message.html, message.text)
    if verify_links:
        lines.append("\n🔗 *Verification Link:*")
        for link in verify_links[:3]:  # Limit to 3 links
            lines.append(link)

    text = "\n".join(lines)
    success = send_telegram_message(text)

    if success:
        print(f"  ✓ Telegram notification sent for: {message.subject!r}")
    else:
        print(f"  ✗ Failed to send Telegram notification for: {message.subject!r}")
        # Print to console as fallback
        print(f"\n{text}\n")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    setup_logging(level=logging.INFO)

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️  Warning: Telegram credentials not set.")
        print("   Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID environment variables.")
        print("   Email notifications will be printed to console instead.\n")

    with TempMailClient() as client:
        email = client.generate_email()

        print("=" * 60)
        print("📬 Telegram Email Notifier")
        print("=" * 60)
        print(f"Monitoring: {email.address}")
        print("Waiting for emails... (Press Ctrl+C to stop)")
        print()

        # Send a startup notification to Telegram
        send_telegram_message(
            f"🚀 *TempMail Monitor Started*\n"
            f"*Address:* `{email.address}`\n"
            f"_Send an email here to receive a Telegram notification._"
        )

        try:
            client.monitor(email.address, callback=on_new_email)
        except KeyboardInterrupt:
            print("\nMonitoring stopped.")
            send_telegram_message("⏹️ *TempMail Monitor Stopped.*")


if __name__ == "__main__":
    main()
