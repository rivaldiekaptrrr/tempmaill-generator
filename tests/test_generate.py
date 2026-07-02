"""
Tests for email generation (generate_email endpoint).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from tempmail import TempMailClient
from tempmail.exceptions import APIError, ConnectionError, ParsingError
from tempmail.models import EmailAddress


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def client() -> TempMailClient:
    """Return a fresh TempMailClient with retries disabled for tests."""
    from tempmail.config import TempMailConfig

    cfg = TempMailConfig(retry_max_attempts=1)
    return TempMailClient(config=cfg)


def _mock_post_response(json_data: dict) -> MagicMock:
    """Create a mock requests.Response for POST."""
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.json.return_value = json_data
    resp.request = MagicMock()
    resp.request.method = "POST"
    resp.url = "https://cleantempmail.com/api/generate-email"
    return resp


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------


class TestGenerateEmail:
    def test_returns_email_address_object(self, client: TempMailClient) -> None:
        """generate_email() should return an EmailAddress instance."""
        mock_resp = _mock_post_response(
            {"success": True, "data": {"email": "test@example.com"}}
        )
        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.generate_email()

        assert isinstance(result, EmailAddress)
        assert result.address == "test@example.com"
        assert result.username == "test"
        assert result.domain == "example.com"

    def test_email_address_split(self, client: TempMailClient) -> None:
        """Username and domain are correctly split from the full address."""
        mock_resp = _mock_post_response(
            {"success": True, "data": {"email": "hello.world@my-domain.co.uk"}}
        )
        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.generate_email()

        assert result.username == "hello.world"
        assert result.domain == "my-domain.co.uk"

    def test_raises_parsing_error_on_missing_email_field(
        self, client: TempMailClient
    ) -> None:
        """generate_email() should raise ParsingError when 'email' key is absent."""
        mock_resp = _mock_post_response({"success": True, "data": {}})
        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(ParsingError):
                client.generate_email()

    def test_raises_api_error_on_non_2xx(self, client: TempMailClient) -> None:
        """generate_email() should raise APIError on non-2xx HTTP status."""
        mock_resp = MagicMock()
        mock_resp.ok = False
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"message": "Internal Server Error"}
        mock_resp.text = "Internal Server Error"
        mock_resp.request = MagicMock()
        mock_resp.request.method = "POST"
        mock_resp.url = "https://cleantempmail.com/api/generate-email"

        with patch.object(client._session, "post", return_value=mock_resp):
            with pytest.raises(APIError):
                client.generate_email()

    def test_raises_connection_error_on_network_failure(
        self, client: TempMailClient
    ) -> None:
        """generate_email() should raise ConnectionError on network failure."""
        import requests as req_lib

        with patch.object(
            client._session,
            "post",
            side_effect=req_lib.exceptions.ConnectionError("DNS failure"),
        ):
            with pytest.raises(ConnectionError):
                client.generate_email()

    def test_context_manager(self) -> None:
        """TempMailClient should work as a context manager."""
        with TempMailClient() as c:
            assert isinstance(c, TempMailClient)

    def test_created_at_is_populated(self, client: TempMailClient) -> None:
        """generated email should have a created_at timestamp."""
        from datetime import datetime

        mock_resp = _mock_post_response(
            {"success": True, "data": {"email": "ts@example.com"}}
        )
        with patch.object(client._session, "post", return_value=mock_resp):
            result = client.generate_email()

        assert isinstance(result.created_at, datetime)
