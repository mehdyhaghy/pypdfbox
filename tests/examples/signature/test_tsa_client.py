"""Tests for ``TSAClient``."""

from __future__ import annotations

import hashlib
from io import BytesIO

from pypdfbox.examples.signature.tsa_client import TSAClient


def test_uses_transport_seam():
    captured = {}

    def fake_transport(request, url, headers):
        captured["request"] = request
        captured["url"] = url
        captured["headers"] = dict(headers)
        return b"token-bytes"

    client = TSAClient(
        url="http://tsa.test.invalid",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=fake_transport,
    )
    token = client.get_time_stamp_token(BytesIO(b"hello"))
    assert token == b"token-bytes"
    assert captured["url"] == "http://tsa.test.invalid"
    assert captured["headers"]["Content-Type"] == "application/timestamp-query"
    assert b"sha256" in captured["request"]


def test_basic_auth_header_set_when_credentials_provided():
    captured = {}

    def fake_transport(request, url, headers):
        captured["headers"] = dict(headers)
        return b""

    client = TSAClient(
        "http://tsa.test.invalid",
        "user",
        "pass",
        hashlib.sha256(),
        transport=fake_transport,
    )
    client.get_time_stamp_token(BytesIO(b""))
    assert "Authorization" in captured["headers"]
    assert captured["headers"]["Authorization"].startswith("Basic ")
