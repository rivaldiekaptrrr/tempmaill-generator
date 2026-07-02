"""
Tests for the get_domains endpoint.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from tempmail import TempMailClient
from tempmail.exceptions import APIError, ParsingError


@pytest.fixture
def client() -> TempMailClient:
    from tempmail.config import TempMailConfig

    cfg = TempMailConfig(retry_max_attempts=1)
    return TempMailClient(config=cfg)


def _mock_get_response(json_data: dict, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.ok = status < 400
    resp.status_code = status
    resp.json.return_value = json_data
    resp.text = str(json_data)
    resp.request = MagicMock()
    resp.request.method = "GET"
    resp.url = "https://cleantempmail.com/api/domains"
    return resp


class TestGetDomains:
    def test_returns_list_of_strings(self, client: TempMailClient) -> None:
        payload = {
            "success": True,
            "data": {
                "domains": ["example.com", "test.org", "mail.io"],
                "limit": 3,
                "offset": 0,
                "total": 958,
            },
        }
        resp = _mock_get_response(payload)
        with patch.object(client._session, "get", return_value=resp):
            result = client.get_domains(limit=3)

        assert isinstance(result, list)
        assert result == ["example.com", "test.org", "mail.io"]

    def test_empty_domains_list(self, client: TempMailClient) -> None:
        payload = {"success": True, "data": {"domains": [], "total": 0}}
        resp = _mock_get_response(payload)
        with patch.object(client._session, "get", return_value=resp):
            result = client.get_domains()

        assert result == []

    def test_default_limit_used_when_not_specified(
        self, client: TempMailClient
    ) -> None:
        """get_domains() should use the config default when limit is not passed."""
        payload = {
            "success": True,
            "data": {"domains": ["a.com"], "total": 1},
        }
        resp = _mock_get_response(payload)
        with patch.object(client._session, "get", return_value=resp) as mock_get:
            client.get_domains()

        call_kwargs = mock_get.call_args
        assert call_kwargs is not None
        params = call_kwargs.kwargs.get("params") or (
            call_kwargs.args[1] if len(call_kwargs.args) > 1 else {}
        )
        assert "limit" in str(params)

    def test_raises_parsing_error_on_non_list_domains(
        self, client: TempMailClient
    ) -> None:
        payload = {"success": True, "data": {"domains": "not-a-list"}}
        resp = _mock_get_response(payload)
        with patch.object(client._session, "get", return_value=resp):
            with pytest.raises(ParsingError):
                client.get_domains()

    def test_raises_api_error_on_server_error(self, client: TempMailClient) -> None:
        resp = _mock_get_response({"message": "error"}, status=503)
        with patch.object(client._session, "get", return_value=resp):
            with pytest.raises(APIError):
                client.get_domains()

    def test_domain_count_matches_list_length(self, client: TempMailClient) -> None:
        domains = [f"domain{i}.com" for i in range(20)]
        payload = {
            "success": True,
            "data": {"domains": domains, "total": 20},
        }
        resp = _mock_get_response(payload)
        with patch.object(client._session, "get", return_value=resp):
            result = client.get_domains(limit=20)

        assert len(result) == 20
