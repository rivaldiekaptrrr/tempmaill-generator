"""
Parser module for extracting useful data from email content.

Provides functions to:
- Extract all hyperlinks from HTML
- Extract OTP codes (4/5/6/8 digits) from text or HTML
- Extract verification/confirmation URLs from email body
"""

from __future__ import annotations

import logging
import re
from typing import Optional

from bs4 import BeautifulSoup

from tempmail.constants import LOGGER_NAME, OTP_DIGIT_LENGTHS
from tempmail.exceptions import ParsingError

logger = logging.getLogger(LOGGER_NAME)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

# Pre-compiled OTP regex patterns keyed by digit length (longest first).
# The word-boundary anchors ensure we don't match substrings of longer numbers.
_OTP_PATTERNS: dict[int, re.Pattern[str]] = {
    length: re.compile(rf"(?<!\d)(\d{{{length}}})(?!\d)")
    for length in OTP_DIGIT_LENGTHS
}

# Pattern for absolute https:// URLs
_URL_PATTERN = re.compile(
    r"https?://"
    r"(?:[A-Za-z0-9\-]+\.)+[A-Za-z]{2,}"
    r"(?:/[^\"'\s<>]*)?"
)

# Keywords that hint a URL is a verification / confirmation link
_VERIFICATION_KEYWORDS = re.compile(
    r"verif|confirm|activate|activation|validate|reset|click|auth|token|magic",
    re.IGNORECASE,
)


def _parse_html(html: str) -> BeautifulSoup:
    """Parse an HTML string with lxml (falls back to html.parser).

    Args:
        html: Raw HTML content.

    Returns:
        A :class:`BeautifulSoup` instance.

    Raises:
        ParsingError: If the HTML cannot be parsed at all.
    """
    try:
        return BeautifulSoup(html, "lxml")
    except Exception:
        try:
            return BeautifulSoup(html, "html.parser")
        except Exception as exc:
            raise ParsingError(
                f"Failed to parse HTML: {exc}", raw=html[:200]
            ) from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_links(html: str) -> list[str]:
    """Extract all unique hyperlinks from an HTML string.

    Args:
        html: Raw HTML content.

    Returns:
        Deduplicated list of ``href`` values found in ``<a>`` tags.
        Relative links and ``mailto:`` links are included as-is.

    Raises:
        ParsingError: If *html* cannot be parsed.
    """
    if not html:
        return []

    soup = _parse_html(html)
    seen: set[str] = set()
    links: list[str] = []

    for tag in soup.find_all("a", href=True):
        href: str = tag["href"].strip()
        if href and href not in seen:
            seen.add(href)
            links.append(href)

    logger.debug("extract_links: found %d unique links", len(links))
    return links


def extract_otp(text: str, html: str = "") -> Optional[str]:
    """Search for a standalone OTP code in the email body.

    Searches plain text first, then falls back to the stripped HTML text.
    Checks digit lengths in order: 8, 6, 5, 4 (longest match wins).

    Args:
        text: Plain-text body of the email.
        html: HTML body of the email (optional fallback).

    Returns:
        The OTP code as a string, or ``None`` if none is found.
    """
    sources: list[str] = []
    if text:
        sources.append(text)
    if html:
        soup = _parse_html(html)
        stripped = soup.get_text(separator=" ")
        if stripped:
            sources.append(stripped)

    for source in sources:
        for length in OTP_DIGIT_LENGTHS:
            pattern = _OTP_PATTERNS[length]
            match = pattern.search(source)
            if match:
                otp = match.group(1)
                logger.debug("extract_otp: found %d-digit OTP %r", length, otp)
                return otp

    logger.debug("extract_otp: no OTP found")
    return None


def extract_verification_urls(html: str, text: str = "") -> list[str]:
    """Extract URLs that look like verification or confirmation links.

    Scans both HTML anchor tags and raw text for URLs whose href or text
    contains verification-related keywords.

    Args:
        html: HTML body of the email.
        text: Plain-text body of the email (optional supplement).

    Returns:
        Deduplicated list of candidate verification URLs (``https://...``).
    """
    candidates: set[str] = set()

    # --- HTML pass ---
    if html:
        soup = _parse_html(html)
        for tag in soup.find_all("a", href=True):
            href: str = tag["href"].strip()
            link_text: str = tag.get_text()
            if href.startswith("http") and (
                _VERIFICATION_KEYWORDS.search(href)
                or _VERIFICATION_KEYWORDS.search(link_text)
            ):
                candidates.add(href)

        # Also scan raw text inside the HTML for bare URLs
        raw_text = soup.get_text(separator=" ")
        for url in _URL_PATTERN.findall(raw_text):
            if _VERIFICATION_KEYWORDS.search(url):
                candidates.add(url)

    # --- Plain-text pass ---
    if text:
        for url in _URL_PATTERN.findall(text):
            if _VERIFICATION_KEYWORDS.search(url):
                candidates.add(url)

    result = sorted(candidates)
    logger.debug(
        "extract_verification_urls: found %d candidate URLs", len(result)
    )
    return result
