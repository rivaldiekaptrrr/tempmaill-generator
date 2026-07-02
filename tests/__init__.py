"""
Tests for __init__.py — package-level imports and version.
"""

from __future__ import annotations


class TestPackageExports:
    def test_client_importable(self) -> None:
        from tempmail import TempMailClient

        assert TempMailClient is not None

    def test_config_importable(self) -> None:
        from tempmail import TempMailConfig, default_config

        assert TempMailConfig is not None
        assert default_config is not None

    def test_models_importable(self) -> None:
        from tempmail import EmailAddress, EmailMessage, Attachment

        assert EmailAddress is not None
        assert EmailMessage is not None
        assert Attachment is not None

    def test_exceptions_importable(self) -> None:
        from tempmail import (
            TempMailException,
            APIError,
            RateLimitError,
            EmailNotFound,
            ConnectionError,
            ParsingError,
        )

        assert issubclass(APIError, TempMailException)
        assert issubclass(RateLimitError, TempMailException)
        assert issubclass(EmailNotFound, TempMailException)
        assert issubclass(ConnectionError, TempMailException)
        assert issubclass(ParsingError, TempMailException)

    def test_parser_functions_importable(self) -> None:
        from tempmail import extract_links, extract_otp, extract_verification_urls

        assert callable(extract_links)
        assert callable(extract_otp)
        assert callable(extract_verification_urls)

    def test_monitor_async_importable(self) -> None:
        from tempmail import monitor_async

        assert callable(monitor_async)

    def test_setup_logging_importable(self) -> None:
        from tempmail import setup_logging

        assert callable(setup_logging)

    def test_version_attribute(self) -> None:
        import tempmail

        assert hasattr(tempmail, "__version__")
        assert isinstance(tempmail.__version__, str)
