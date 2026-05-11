"""Tests for ``CreateVisibleSignature``."""

from __future__ import annotations

from pypdfbox.examples.signature.create_visible_signature import (
    CreateVisibleSignature,
)


def test_extends_create_signature_base(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    assert signer.get_certificate_chain()


def test_late_external_signing_flag(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    assert signer.is_late_external_signing() is False
    signer.set_late_external_signing(True)
    assert signer.is_late_external_signing() is True


def test_visible_signature_properties_captured(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.set_visible_signature_properties(
        "Jane", "Earth", "Testing", preferred_size=0
    )
    assert signer._visible_signature_properties["name"] == "Jane"


def test_visible_sign_designer_captured(pkcs12_bytes, tsa_password):
    signer = CreateVisibleSignature(pkcs12_bytes, tsa_password)
    signer.set_visible_sign_designer(filename=None, x=10, y=20, zoom_percent=100)
    assert signer._visible_sign_designer["x"] == 10
