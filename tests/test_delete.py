"""
Tests for the delete_message endpoint.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from tempmail import TempMailClient
from tempmail.exceptions import EmailNotFound, APIError


@pytest.fixture
def client() -> TempMailClient:
    from tempmail.config import TempMailConfig

    cfg = TempMailConfig(retry_max_attempts=1)
    return TempMailClient(config=cfg)


def _mock_delete_response(json_data: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.ok = status < 400
    resp.status_code = status
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.request = MagicMock()
    resp.request.method = "DELETE"
    resp.url = "https://cleantempmail.com/api/email/msg1"
    return resp


class TestDeleteMessage:
    def test_returns_true_on_success(self, client: TempMailClient) -> None:
        resp = _mock_delete_response({"success": True})
        with patch.object(client._session, "delete", return_value=resp):
            result = client.delete_message("msg1")

        assert result is True

    def test_raises_email_not_found_on_404(self, client: TempMailClient) -> None:
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 404
        resp.request = MagicMock()
        resp.request.method = "DELETE"
        resp.url = "https://cleantempmail.com/api/email/ghost"

        with patch.object(client._session, "delete", return_value=resp):
            with pytest.raises(EmailNotFound) as exc_info:
                client.delete_message("ghost")

        assert exc_info.value.email_id == "ghost"
        assert exc_info.value.status_code == 404

    def test_raises_api_error_on_server_error(self, client: TempMailClient) -> None:
        resp = _mock_delete_response({"message": "Internal error"}, status=500)
        with patch.object(client._session, "delete", return_value=resp):
            with pytest.raises(APIError):
                client.delete_message("msg1")

    def test_handles_empty_success_body(self, client: TempMailClient) -> None:
        """An empty body with 200 status should still return True."""
        resp = _mock_delete_response({}, status=200)
        with patch.object(client._session, "delete", return_value=resp):
            result = client.delete_message("msg1")

        assert result is True

    def test_email_not_found_has_correct_attributes(
        self, client: TempMailClient
    ) -> None:
        resp = MagicMock()
        resp.ok = False
        resp.status_code = 404
        resp.request = MagicMock()
        resp.request.method = "DELETE"
        resp.url = "https://cleantempmail.com/api/email/id123"

        with patch.object(client._session, "delete", return_value=resp):
            try:
                client.delete_message("id123")
            except EmailNotFound as exc:
                assert exc.email_id == "id123"
                assert "id123" in str(exc)
