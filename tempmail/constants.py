"""
Constants for the TempMail library.

All hardcoded values are defined here to maintain a clean architecture
and make configuration changes easy.
"""

# Base URL
BASE_URL: str = "https://cleantempmail.com"

# Default request headers to mimic a real browser
DEFAULT_HEADERS: dict[str, str] = {
    "Origin": "https://cleantempmail.com",
    "Referer": "https://cleantempmail.com/",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

# API Endpoints
ENDPOINT_GENERATE_EMAIL: str = "/api/generate-email"
ENDPOINT_DOMAINS: str = "/api/domains"
ENDPOINT_INBOX: str = "/api/emails"
ENDPOINT_EMAIL: str = "/api/email"
ENDPOINT_EVENTS: str = "/api/events"

# Retry policy
RETRY_MAX_ATTEMPTS: int = 3
RETRY_BASE_DELAY: float = 1.0  # seconds
RETRY_EXPONENTIAL_BASE: int = 2

# Default request timeout in seconds
DEFAULT_TIMEOUT: int = 30

# Default limit for domain listing
DEFAULT_DOMAINS_LIMIT: int = 100

# SSE event types
SSE_EVENT_NEW_EMAIL: str = "new_email"
SSE_EVENT_PING: str = "ping"
SSE_EVENT_CONNECTED: str = "connected"

# OTP patterns - digit lengths to detect
OTP_DIGIT_LENGTHS: tuple[int, ...] = (8, 6, 5, 4)

# Logger name
LOGGER_NAME: str = "tempmail"
