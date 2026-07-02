"""
Example: Delete an email message.

Usage:
    python examples/delete_email.py
"""

import logging

from tempmail import EmailNotFound, TempMailClient, setup_logging


def main() -> None:
    setup_logging(level=logging.INFO)

    with TempMailClient() as client:
        # Generate a new email and check inbox
        email = client.generate_email()
        print(f"Email: {email.address}\n")

        messages = client.get_messages(email.address)

        if not messages:
            print("Inbox is empty. Nothing to delete.")
            print("Tip: Send an email to this address first, then run this example.")
            return

        print(f"Found {len(messages)} message(s):")
        for idx, msg in enumerate(messages, start=1):
            print(f"  [{idx}] ID={msg.id}  Subject={msg.subject!r}")

        # Delete each message
        print("\nDeleting all messages...")
        deleted = 0
        skipped = 0

        for msg in messages:
            try:
                success = client.delete_message(msg.id)
                if success:
                    print(f"  ✓ Deleted: {msg.id}")
                    deleted += 1
                else:
                    print(f"  ✗ Could not delete: {msg.id}")
                    skipped += 1
            except EmailNotFound:
                print(f"  ✗ Already gone: {msg.id}")
                skipped += 1

        print(f"\nDone. Deleted: {deleted}  Skipped: {skipped}")

        # Verify inbox is now empty
        remaining = client.get_messages(email.address)
        print(f"Inbox now has {len(remaining)} message(s).")


if __name__ == "__main__":
    main()
