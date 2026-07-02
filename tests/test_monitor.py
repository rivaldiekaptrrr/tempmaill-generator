"""
Tests for the get_messages (inbox) endpoint.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from tempmail import TempMailClient
from tempmail.models import EmailMessage


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
    resp.url = "https://cleantempmail.com/api/emails"
    return resp


SAMPLE_INBOX = {
    "success": True,
    "data": {
        "emails": [
            {
                "id": "email1",
                "from": "alice@example.com",
                "to": "me@tempmail.com",
                "subject": "Hello",
                "text": "Hi there!",
                "html": "<p>Hi there!</p>",
                "date": "2024-06-01T10:00:00Z",
            },
            {
                "id": "email2",
                "from": "bob@example.com",
                "to": "me@tempmail.com",
                "subject": "Your verification code",
                "text": "Code: 654321",
                "html": "<b>654321</b>",
                "date": "2024-06-01T11:00:00Z",
            },
        ],
        "count": 2,
    },
}


class TestGetMessages:
    def test_returns_list_of_email_messages(self, client: TempMailClient) -> None:
        resp = _mock_response(SAMPLE_INBOX)
        with patch.object(client._session, "get", return_value=resp):
            messages = client.get_messages("me@tempmail.com")

        assert isinstance(messages, list)
        assert len(messages) == 2
        assert all(isinstance(m, EmailMessage) for m in messages)

    def test_empty_inbox_returns_empty_list(self, client: TempMailClient) -> None:
        payload = {"success": True, "data": {"emails": [], "count": 0}}
        resp = _mock_response(payload)
        with patch.object(client._session, "get", return_value=resp):
            messages = client.get_messages("empty@tempmail.com")

        assert messages == []

    def test_message_fields_mapped_correctly(self, client: TempMailClient) -> None:
        resp = _mock_response(SAMPLE_INBOX)
        with patch.object(client._session, "get", return_value=resp):
            messages = client.get_messages("me@tempmail.com")

        first = messages[0]
        assert first.id == "email1"
        assert first.sender == "alice@example.com"
        assert first.subject == "Hello"

    def test_malformed_item_is_skipped_not_crash(self, client: TempMailClient) -> None:
        """A single unparseable email item should be skipped with a warning."""
        payload = {
            "success": True,
            "data": {
                "emails": [
                    # Missing required 'id' and 'from' fields → should be skipped
                    {"subject": "No ID or From"},
                    {
                        "id": "valid1",
                        "from": "ok@example.com",
                        "subject": "Valid",
                        "text": "",
                        "html": "",
                    },
                ],
                "count": 2,
            },
        }
        resp = _mock_response(payload)
        with patch.object(client._session, "get", return_value=resp):
            messages = client.get_messages("me@tempmail.com")

        # At least the valid one should be present
        assert any(m.id == "valid1" for m in messages)
