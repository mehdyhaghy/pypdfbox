from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSignature,
    SignatureValidationResult,
)


def test_verify_invalid_pkcs7_blob_fails_gracefully() -> None:
    """64 zero bytes are not valid PKCS#7 — verify() must fail gracefully
    with is_valid=False and at least one error string."""
    sig = PDSignature()
    sig.set_byte_range([0, 4, 200, 4])
    sig.set_contents(b"\x00" * 64)

    document = b"AAAA" + b"x" * 196 + b"BBBB"
    result = sig.verify(document)

    assert isinstance(result, SignatureValidationResult)
    assert result.is_valid is False
    assert result.errors
    # digest is computed over /ByteRange even when PKCS#7 parse fails
    assert result.computed_digest == hashlib.sha256(b"AAAABBBB").digest()


def test_verify_missing_byte_range_returns_error() -> None:
    sig = PDSignature()
    sig.set_contents(b"\x00" * 64)
    result = sig.verify(b"some document bytes")
    assert result.is_valid is False
    assert any("/ByteRange" in e for e in result.errors)


def test_verify_missing_contents_returns_error() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 4, 8, 4])
    result = sig.verify(b"AAAAxxxxBBBB")
    assert result.is_valid is False
    assert any("/Contents" in e for e in result.errors)


def test_get_signed_data_concatenates_byte_range_slices() -> None:
    sig = PDSignature()
    sig.set_byte_range([0, 10, 20, 5])

    document = (
        b"0123456789"  # bytes 0..9    (range 1: start1=0, len1=10)
        b"##########"  # bytes 10..19  (skipped — /Contents placeholder)
        b"ABCDE"  # bytes 20..24       (range 2: start2=20, len2=5)
    )
    assert len(document) == 25
    assert sig.get_signed_data(document) == b"0123456789ABCDE"


def test_get_signed_data_returns_none_without_byte_range() -> None:
    sig = PDSignature()
    assert sig.get_signed_data(b"anything") is None


def test_get_contents_bytes_alias_returns_decoded_contents() -> None:
    sig = PDSignature()
    assert sig.get_contents_bytes() is None
    sig.set_contents(b"\x01\x02\x03\x04")
    assert sig.get_contents_bytes() == b"\x01\x02\x03\x04"


def test_signature_validation_result_round_trips_fields() -> None:
    when = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)
    r = SignatureValidationResult(
        is_valid=True,
        signer_certificate=object(),
        signer_subject="CN=Alice,O=Example",
        signer_serial_number=12345,
        signed_digest=b"\xaa" * 32,
        computed_digest=b"\xaa" * 32,
        signing_time=when,
        errors=[],
    )

    assert r.is_valid is True
    assert r.signer_certificate is not None
    assert r.signer_subject == "CN=Alice,O=Example"
    assert r.signer_serial_number == 12345
    assert r.signed_digest == b"\xaa" * 32
    assert r.computed_digest == b"\xaa" * 32
    assert r.signing_time == when
    assert r.errors == []


def test_signature_validation_result_default_is_failure() -> None:
    r = SignatureValidationResult()
    assert r.is_valid is False
    assert r.signer_certificate is None
    assert r.signer_subject is None
    assert r.signer_serial_number is None
    assert r.signed_digest is None
    assert r.computed_digest is None
    assert r.signing_time is None
    assert r.errors == []


def test_signature_validation_result_errors_independent_per_instance() -> None:
    """Default mutable list must not leak between instances."""
    a = SignatureValidationResult()
    b = SignatureValidationResult()
    a.errors.append("boom")
    assert b.errors == []
