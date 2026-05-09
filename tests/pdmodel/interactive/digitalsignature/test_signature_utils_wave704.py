from __future__ import annotations

import hashlib

from cryptography.x509 import ExtensionNotFound

from pypdfbox.pdmodel.interactive.digitalsignature import sig_utils
from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature

_TIME_STAMPING_EKU = "1.3.6.1.5.5.7.3.8"


class _Extensions:
    def __init__(self, value: object | None = None) -> None:
        self._value = value

    def get_extension_for_oid(self, oid: object) -> object:
        if self._value is None:
            raise ExtensionNotFound("missing", oid)
        return type("Extension", (), {"value": self._value})()


class _Certificate:
    def __init__(self, eku_oids: list[str] | None) -> None:
        usages = [type("Usage", (), {"dotted_string": oid})() for oid in eku_oids or []]
        self.extensions = _Extensions(usages if eku_oids is not None else None)


def test_private_eku_helper_reports_missing_and_matching_usage() -> None:
    assert (
        sig_utils._has_extended_key_usage(  # noqa: SLF001
            _Certificate(None), _TIME_STAMPING_EKU
        )
        is False
    )
    assert (
        sig_utils._has_extended_key_usage(  # noqa: SLF001
            _Certificate([_TIME_STAMPING_EKU]),
            _TIME_STAMPING_EKU,
        )
        is True
    )


def test_extract_pkcs7_message_digest_returns_none_for_truncated_lengths() -> None:
    oid_der = bytes.fromhex("06092A864886F70D010904")

    assert sig_utils.extract_pkcs7_message_digest(oid_der + b"\x31") is None
    assert sig_utils.extract_pkcs7_message_digest(oid_der + b"\x31\x05abc") is None


def test_verify_reports_pkcs7_with_no_certificates(monkeypatch) -> None:
    from cryptography.hazmat.primitives.serialization import pkcs7

    monkeypatch.setattr(pkcs7, "load_der_pkcs7_certificates", lambda _der: [])
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])
    sig.set_contents(b"fake-der")

    result = sig.verify(b"HEADxxxxTAIL")

    assert result.is_valid is False
    assert result.errors == ["no certificates in PKCS#7 SignedData"]
    assert result.computed_digest == hashlib.sha256(b"HEADTAIL").digest()


def test_verify_handles_certificate_metadata_and_digest_extraction_failures(
    monkeypatch,
) -> None:
    from cryptography.hazmat.primitives.serialization import pkcs7

    class Subject:
        def rfc4514_string(self) -> str:
            raise ValueError("bad subject")

    class Certificate:
        subject = Subject()
        serial_number = object()

    def raise_from_digest(_der: bytes) -> bytes:
        raise ValueError("bad digest")

    monkeypatch.setattr(
        pkcs7, "load_der_pkcs7_certificates", lambda _der: [Certificate()]
    )
    monkeypatch.setattr(sig_utils, "extract_pkcs7_message_digest", raise_from_digest)
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])
    sig.set_contents(b"fake-der")

    result = sig.verify(b"HEADxxxxTAIL")

    assert result.signer_subject is None
    assert result.signer_serial_number is None
    assert result.signed_digest is None
    assert result.is_valid is False
    assert result.errors[0] == "failed to recover messageDigest: bad digest"
    assert "messageDigest signed-attribute not found in PKCS#7" in result.errors[1]
