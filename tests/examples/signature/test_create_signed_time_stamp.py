"""Tests for ``CreateSignedTimeStamp``."""

from __future__ import annotations

from io import BytesIO

from pypdfbox.examples.signature.create_signed_time_stamp import CreateSignedTimeStamp


def test_sign_uses_validation_time_stamp(monkeypatch):
    signer = CreateSignedTimeStamp("http://tsa.test.invalid")

    captured = {}

    class FakeValidation:
        def __init__(self, url):
            captured["url"] = url

        def get_time_stamp_token(self, content):
            captured["payload"] = content.read()
            return b"FAKE-TOKEN"

    monkeypatch.setattr(
        "pypdfbox.examples.signature.create_signed_time_stamp.ValidationTimeStamp",
        FakeValidation,
    )
    result = signer.sign(BytesIO(b"to-stamp"))
    assert result == b"FAKE-TOKEN"
    assert captured["url"] == "http://tsa.test.invalid"
    assert captured["payload"] == b"to-stamp"


def test_implements_signature_interface_sign():
    signer = CreateSignedTimeStamp("http://tsa.test.invalid")
    assert callable(signer.sign)
