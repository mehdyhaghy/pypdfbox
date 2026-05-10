from __future__ import annotations

import hashlib
from datetime import UTC, datetime

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
    when = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
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


# ---------------------------------------------------------------------------
# SignatureValidationResult — predicate helpers (Wave 256)
# ---------------------------------------------------------------------------


def test_signature_validation_result_has_errors_default_false() -> None:
    r = SignatureValidationResult()
    assert r.has_errors() is False


def test_signature_validation_result_has_errors_true_after_append() -> None:
    r = SignatureValidationResult()
    r.errors.append("PKCS#7 parse failed")
    assert r.has_errors() is True


def test_signature_validation_result_has_signer_default_false() -> None:
    r = SignatureValidationResult()
    assert r.has_signer() is False


def test_signature_validation_result_has_signer_true_when_cert_set() -> None:
    r = SignatureValidationResult(signer_certificate=object())
    assert r.has_signer() is True


def test_signature_validation_result_has_signed_digest_default_false() -> None:
    r = SignatureValidationResult()
    assert r.has_signed_digest() is False


def test_signature_validation_result_has_signed_digest_true_when_set() -> None:
    r = SignatureValidationResult(signed_digest=b"\xaa" * 32)
    assert r.has_signed_digest() is True


def test_signature_validation_result_has_signed_digest_true_for_empty_bytes() -> None:
    """An empty-bytes ``signed_digest`` is still "present" — only ``None``
    means "not recovered". An empty digest is degenerate but distinguishable
    from a missing OID scan, and the predicate must reflect that."""
    r = SignatureValidationResult(signed_digest=b"")
    assert r.has_signed_digest() is True


def test_signature_validation_result_has_computed_digest_default_false() -> None:
    r = SignatureValidationResult()
    assert r.has_computed_digest() is False


def test_signature_validation_result_has_computed_digest_true_when_set() -> None:
    r = SignatureValidationResult(computed_digest=b"\xbb" * 32)
    assert r.has_computed_digest() is True


def test_signature_validation_result_digest_matches_default_false() -> None:
    """Both digests absent -> not a match (verify hasn't run far enough)."""
    r = SignatureValidationResult()
    assert r.digest_matches() is False


def test_signature_validation_result_digest_matches_true_when_equal() -> None:
    digest = b"\xcc" * 32
    r = SignatureValidationResult(signed_digest=digest, computed_digest=digest)
    assert r.digest_matches() is True


def test_signature_validation_result_digest_matches_false_when_unequal() -> None:
    r = SignatureValidationResult(
        signed_digest=b"\xcc" * 32,
        computed_digest=b"\xdd" * 32,
    )
    assert r.digest_matches() is False


def test_signature_validation_result_digest_matches_false_when_one_missing() -> None:
    """If only one digest was recovered, ``digest_matches`` must not raise
    nor compare ``None`` to bytes — it returns ``False``."""
    r1 = SignatureValidationResult(signed_digest=b"\xaa" * 32)
    assert r1.has_computed_digest() is False
    assert r1.digest_matches() is False

    r2 = SignatureValidationResult(computed_digest=b"\xaa" * 32)
    assert r2.has_signed_digest() is False
    assert r2.digest_matches() is False


def test_signature_validation_result_digest_matches_distinguishes_from_missing() -> None:
    """Two valid byte strings of different length must surface as mismatch
    — the equality check must not accidentally collapse to ``False`` via
    truthiness only when one digest is empty."""
    r = SignatureValidationResult(signed_digest=b"", computed_digest=b"\xaa")
    assert r.has_signed_digest() is True
    assert r.has_computed_digest() is True
    assert r.digest_matches() is False


def test_signature_validation_result_add_error_appends_and_clears_valid() -> None:
    """``add_error`` is the one-line "record-error-and-fail" idiom used by
    every failure path in :meth:`PDSignature.verify`."""
    r = SignatureValidationResult(is_valid=True)
    r.add_error("missing /ByteRange")
    assert r.is_valid is False
    assert r.errors == ["missing /ByteRange"]
    assert r.has_errors() is True


def test_signature_validation_result_add_error_accumulates() -> None:
    """Multiple ``add_error`` calls accumulate. Validity stays ``False``
    after the first call regardless of subsequent additions."""
    r = SignatureValidationResult()
    r.add_error("first")
    r.add_error("second")
    r.add_error("third")
    assert r.errors == ["first", "second", "third"]
    assert r.is_valid is False
    assert r.has_errors() is True


def test_signature_validation_result_add_error_does_not_revive_valid() -> None:
    """Once an error is recorded, the result stays invalid even if the
    caller mutates ``is_valid`` back to ``True`` afterwards. The mutator
    contract is "clear validity at error time" — long-term enforcement is
    the caller's responsibility."""
    r = SignatureValidationResult(is_valid=True)
    r.add_error("boom")
    assert r.is_valid is False
    # Caller-induced revival is not blocked, but the error stays.
    r.is_valid = True
    assert r.has_errors() is True


# ---------------------------------------------------------------------------
# End-to-end: real PKCS#7 detached signature → digest-match verify
# ---------------------------------------------------------------------------


def _make_self_signed_signer():
    """Self-signed cert + key pair for a Pkcs7Signature roundtrip test."""
    import datetime as _dt

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "verify-test")])
    now = _dt.datetime.now(_dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(42)
        .not_valid_before(now)
        .not_valid_after(now + _dt.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def test_verify_digest_match_against_real_pkcs7_blob() -> None:
    """End-to-end: build a PKCS#7 detached SignedData over the bracketed
    document bytes, splice into a synthetic /Contents slot, then verify()
    — expect digest match, signer cert recovered, signed_digest populated.
    """
    import io as _io

    from pypdfbox.pdmodel.interactive.digitalsignature import (
        Pkcs7Signature,
        compute_byte_range,
    )

    cert, key = _make_self_signed_signer()

    # Synthetic PDF: prefix bytes, a `<...>` placeholder window, suffix bytes.
    # PDFBox-style bracketed bytes (per ISO 32000-1 §12.8.1) INCLUDE the
    # angle brackets — so the signer must hash prefix + b"<" + b">" + suffix.
    prefix = b"%PDF-1.7\n" + b"A" * 100
    suffix = b"B" * 100 + b"\n%%EOF\n"

    signer = Pkcs7Signature(cert, key)
    # First produce a placeholder doc to reserve space.
    placeholder = b"\x00" * 4096
    document_template = prefix + b"<" + placeholder + b">" + suffix
    open_idx = len(prefix)
    close_idx = open_idx + 1 + len(placeholder)
    byte_range = compute_byte_range(document_template, open_idx, close_idx)
    bracketed = (
        document_template[byte_range[0] : byte_range[0] + byte_range[1]]
        + document_template[byte_range[2] : byte_range[2] + byte_range[3]]
    )

    pkcs7_blob = signer.sign(_io.BytesIO(bracketed))
    # Splice into the placeholder window (zero-pad to keep offsets stable).
    if len(pkcs7_blob) > len(placeholder):
        raise AssertionError("placeholder too small for PKCS#7 blob in test")
    splice = pkcs7_blob + b"\x00" * (len(placeholder) - len(pkcs7_blob))
    document = prefix + b"<" + splice + b">" + suffix

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)

    result = sig.verify(document)

    assert result.signer_certificate is not None
    assert result.signer_subject is not None and "verify-test" in result.signer_subject
    assert result.signer_serial_number == 42
    assert result.computed_digest is not None
    assert result.signed_digest is not None
    assert result.signed_digest == result.computed_digest
    assert result.is_valid is True


def test_verify_detects_tampering_via_digest_mismatch() -> None:
    """If the document is altered after signing, verify() must surface a
    digest-mismatch error and is_valid=False."""
    import io as _io

    from pypdfbox.pdmodel.interactive.digitalsignature import (
        Pkcs7Signature,
        compute_byte_range,
    )

    cert, key = _make_self_signed_signer()

    prefix = b"A" * 50
    suffix = b"B" * 50
    placeholder = b"\x00" * 4096
    document_template = prefix + b"<" + placeholder + b">" + suffix
    open_idx = len(prefix)
    close_idx = open_idx + 1 + len(placeholder)
    byte_range = compute_byte_range(document_template, open_idx, close_idx)
    bracketed = (
        document_template[byte_range[0] : byte_range[0] + byte_range[1]]
        + document_template[byte_range[2] : byte_range[2] + byte_range[3]]
    )
    pkcs7_blob = Pkcs7Signature(cert, key).sign(_io.BytesIO(bracketed))
    splice = pkcs7_blob + b"\x00" * (len(placeholder) - len(pkcs7_blob))
    document = prefix + b"<" + splice + b">" + suffix

    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)

    # Tamper with the signed prefix region — flip a byte in the first range.
    tampered = bytearray(document)
    tampered[10] = (tampered[10] + 1) & 0xFF

    result = sig.verify(bytes(tampered))
    assert result.is_valid is False
    assert any("digest mismatch" in e for e in result.errors)
