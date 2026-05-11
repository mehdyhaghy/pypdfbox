"""Tests for ``CreateVisibleSignature2``."""

from __future__ import annotations

from pathlib import Path

from pypdfbox.examples.signature.create_visible_signature2 import (
    CreateVisibleSignature2,
)


def test_image_file_round_trips(pkcs12_bytes, tsa_password, tmp_path: Path):
    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    assert signer.get_image_file() is None
    placeholder = tmp_path / "img.png"
    placeholder.write_bytes(b"\x89PNG\r\n\x1a\n")
    signer.set_image_file(placeholder)
    assert signer.get_image_file() == placeholder
    signer.set_image_file(None)
    assert signer.get_image_file() is None


def test_late_external_signing_round_trip(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature2(pkcs12_bytes, tsa_password)
    assert signer.is_late_external_signing() is False
    signer.set_late_external_signing(True)
    assert signer.is_late_external_signing() is True
