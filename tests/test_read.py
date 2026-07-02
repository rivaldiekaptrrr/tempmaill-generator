"""
Tests for the read_message endpoint and parser utilities.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from tempmail import TempMailClient
from tempmail.exceptions import EmailNotFound, APIError
from tempmail.models import EmailMessage
from tempmail.parser import extract_links, extract_otp, extract_verification_urls


@pytest.fixture
def client() -> TempMailClient:
    from tempmail.config import TempMailConfig

    cfg = TempMailConfig(retry_max_attempts=1)
    return TempMailClient(config=cfg)


def _mock_response(json_data: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.ok = status < 400
    resp.status_code = status
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.request = MagicMock()
    resp.request.method = "GET"
    resp.url = "https://cleantempmail.com/api/email/msg1"
    return resp


SAMPLE_EMAIL_PAYLOAD = {
    "success": True,
    "data": {
        "id": "msg1",
        "from": "sender@example.com",
        "to": "me@tempmail.com",
        "subject": "Verify your account",
        "text": "Click here: https://example.com/verify?token=abc123",
        "html": (
            "<html><body>"
            "<p>Click <a href='https://example.com/verify?token=abc123'>here</a> to verify.</p>"
            "<p>Your OTP is <strong>847291</strong></p>"
            "</body></html>"
        ),
        "date": "2024-01-01T12:00:00Z",
    },
}


class TestReadMessage:
    def test_returns_email_message(self, client: TempMailClient) -> None:
        resp = _mock_response(SAMPLE_EMAIL_PAYLOAD)
        with patch.object(client._session, "get", return_value=resp):
            msg = client.read_message("msg1")

        assert isinstance(msg, EmailMessage)
        assert msg.id == "msg1"
        assert msg.subject == "Verify your account"
        assert msg.sender == "sender@example.com"

    def test_raises_email_not_found_on_404(self, client: TempMailClient) -> None:
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 404
        resp.request = MagicMock()
        resp.request.method = "GET"
        resp.url = "https://cleantempmail.com/api/email/nonexistent"

        with patch.object(client._session, "get", return_value=resp):
            with pytest.raises(EmailNotFound) as exc_info:
                client.read_message("nonexistent")

        assert exc_info.value.email_id == "nonexistent"

    def test_date_parsing_iso_format(self, client: TempMailClient) -> None:
        resp = _mock_response(SAMPLE_EMAIL_PAYLOAD)
        with patch.object(client._session, "get", return_value=resp):
            msg = client.read_message("msg1")

        from datetime import datetime

        assert isinstance(msg.date, datetime)
        assert msg.date.year == 2024

    def test_date_parsing_unix_timestamp(self, client: TempMailClient) -> None:
        payload = dict(SAMPLE_EMAIL_PAYLOAD)
        payload = {
            "success": True,
            "data": {**SAMPLE_EMAIL_PAYLOAD["data"], "date": 1704067200},
        }
        resp = _mock_response(payload)
        with patch.object(client._session, "get", return_value=resp):
            msg = client.read_message("msg1")

        from datetime import datetime

        assert isinstance(msg.date, datetime)


class TestParser:
    """Tests for parser utility functions."""

    SAMPLE_HTML = (
        "<html><body>"
        "<p>Click <a href='https://example.com/verify?token=abc'>Verify</a></p>"
        "<p><a href='https://example.com/unsubscribe'>Unsubscribe</a></p>"
        "<p>Your code: <b>123456</b></p>"
        "</body></html>"
    )

    def test_extract_links_returns_all_hrefs(self) -> None:
        links = extract_links(self.SAMPLE_HTML)
        assert "https://example.com/verify?token=abc" in links
        assert "https://example.com/unsubscribe" in links

    def test_extract_links_deduplicates(self) -> None:
        html = "<a href='https://x.com'>1</a><a href='https://x.com'>2</a>"
        links = extract_links(html)
        assert links.count("https://x.com") == 1

    def test_extract_links_empty_html(self) -> None:
        assert extract_links("") == []

    def test_extract_otp_finds_6_digit(self) -> None:
        otp = extract_otp("Your code: 847291", "")
        assert otp == "847291"

    def test_extract_otp_finds_4_digit(self) -> None:
        otp = extract_otp("PIN: 9823", "")
        assert otp == "9823"

    def test_extract_otp_finds_8_digit(self) -> None:
        otp = extract_otp("Code: 12345678", "")
        assert otp == "12345678"

    def test_extract_otp_prefers_longer_match(self) -> None:
        # Should match 6-digit before 4-digit
        otp = extract_otp("OTP: 123456", "")
        assert otp == "123456"

    def test_extract_otp_returns_none_if_not_found(self) -> None:
        otp = extract_otp("No codes here!", "")
        assert otp is None

    def test_extract_otp_from_html_fallback(self) -> None:
        html = "<b>Your OTP is: 654321</b>"
        otp = extract_otp("", html)
        assert otp == "654321"

    def test_extract_verification_urls_from_html(self) -> None:
        html = (
            "<a href='https://app.com/verify?token=xyz'>Verify Email</a>"
        )
        links = extract_verification_urls(html)
        assert any("verify" in url for url in links)

    def test_extract_verification_urls_from_text(self) -> None:
        text = "Click here to confirm: https://example.com/confirm?t=abc"
        links = extract_verification_urls("", text)
        assert any("confirm" in url for url in links)

    def test_extract_verification_urls_ignores_unrelated(self) -> None:
        html = "<a href='https://example.com/news'>Read more</a>"
        links = extract_verification_urls(html)
        assert links == []
