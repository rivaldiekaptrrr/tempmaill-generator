"""
Example: Read emails from an inbox.

Usage:
    python examples/read_email.py
"""

import logging

from tempmail import TempMailClient, extract_links, extract_otp, extract_verification_urls, setup_logging


def main() -> None:
    setup_logging(level=logging.INFO)

    with TempMailClient() as client:
        # Generate a new email address
        email = client.generate_email()
        print(f"Email: {email.address}\n")

        # Fetch inbox
        messages = client.get_messages(email.address)

        if not messages:
            print("Inbox is empty. Send an email to this address and run again.")
            return

        print(f"Found {len(messages)} message(s) in inbox:\n")

        for idx, msg in enumerate(messages, start=1):
            print(f"[{idx}] {msg.subject} — from {msg.sender}")

        # Read the first message in detail
        first = messages[0]
        print("\n" + "=" * 60)
        print("Reading first message:")
        print("=" * 60)

        # Use read_message to get the full content
        full_msg = client.read_message(first.id)

        print(f"  Subject : {full_msg.subject}")
        print(f"  From    : {full_msg.sender}")
        print(f"  To      : {full_msg.to}")
        if full_msg.date:
            print(f"  Date    : {full_msg.date.strftime('%Y-%m-%d %H:%M:%S')}")
        print()

        if full_msg.text:
            print("--- Plain Text ---")
            print(full_msg.text[:500])

        # Extract useful information
        otp = extract_otp(full_msg.text, full_msg.html)
        if otp:
            print(f"\n🔑 OTP Code: {otp}")

        verify_links = extract_verification_urls(full_msg.html, full_msg.text)
        if verify_links:
            print("\n🔗 Verification Links:")
            for link in verify_links:
                print(f"  {link}")

        all_links = extract_links(full_msg.html)
        if all_links:
            print(f"\n📎 All Links ({len(all_links)} found):")
            for link in all_links[:10]:
                print(f"  {link}")


if __name__ == "__main__":
    main()
