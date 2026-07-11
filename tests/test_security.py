from __future__ import annotations

import hashlib
import hmac
import os

import pytest
from fastapi import Request

from app.security import get_client_ip, hash_ip, valid_verification_token
from app.settings import Settings


@pytest.fixture
def settings() -> Settings:
    return Settings(
        groq_api_key="test-groq-key-not-a-real-secret-000000",
        database_url="postgresql://test:test@127.0.0.1:55432/test",
        frontend_origins=["https://portfolio.example.test"],
        public_api_url="https://api.example.test",
        allowed_hosts=["api.example.test"],
        trusted_proxy_cidrs=["127.0.0.1/32", "172.16.0.0/12", "::1/128"],
        ip_hash_salt="unit-test-ip-hash-salt-000000",
        verify_fallback_token=os.environ["VERIFY_FALLBACK_TOKEN"],
    )


def _request(peer: str, real_ip: str | None = None) -> Request:
    headers = [] if real_ip is None else [(b"x-real-ip", real_ip.encode())]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "https",
            "path": "/",
            "raw_path": b"/",
            "query_string": b"",
            "headers": headers,
            "client": (peer, 12345),
            "server": ("api.example.test", 443),
        }
    )


def test_trusted_proxy_real_ip_is_used_and_normalized(settings: Settings) -> None:
    assert get_client_ip(_request("127.0.0.1", "2001:0db8::0001"), settings) == "2001:db8::1"


def test_untrusted_peer_cannot_spoof_real_ip(settings: Settings) -> None:
    assert get_client_ip(_request("203.0.113.8", "198.51.100.99"), settings) == "203.0.113.8"


def test_invalid_forwarded_ip_falls_back_to_trusted_peer(settings: Settings) -> None:
    assert get_client_ip(_request("172.16.4.2", "not-an-ip"), settings) == "172.16.4.2"


def test_ip_hash_is_a_salted_deterministic_hmac(settings: Settings) -> None:
    ip = "203.0.113.8"
    expected = hmac.new(settings.ip_hash_salt.encode(), ip.encode(), hashlib.sha256).hexdigest()

    assert hash_ip(ip, settings.ip_hash_salt) == expected
    assert hash_ip(ip, settings.ip_hash_salt) != ip
    assert hash_ip(ip, "a-different-salt-that-is-long-enough") != expected


def test_verification_token_uses_exact_nonempty_match(settings: Settings) -> None:
    expected = settings.verify_fallback_token
    assert valid_verification_token(expected, expected) is True
    assert valid_verification_token(None, expected) is False
    assert valid_verification_token("", expected) is False
    assert valid_verification_token(f"{expected}x", expected) is False
