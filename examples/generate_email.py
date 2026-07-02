"""
Example: Generate a temporary email address.

Usage:
    python examples/generate_email.py
"""

import logging
from tempmail import TempMailClient, setup_logging


def main() -> None:
    setup_logging(level=logging.INFO)

    with TempMailClient() as client:
        # Generate a new temporary email address
        email = client.generate_email()

        print("=" * 50)
        print("Temporary Email Generated!")
        print("=" * 50)
        print(f"  Address  : {email.address}")
        print(f"  Username : {email.username}")
        print(f"  Domain   : {email.domain}")
        print(f"  Created  : {email.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        print("=" * 50)

        # List available domains
        domains = client.get_domains(limit=5)
        print(f"\nSample available domains ({len(domains)} shown):")
        for domain in domains:
            print(f"  - {domain}")


if __name__ == "__main__":
    main()
