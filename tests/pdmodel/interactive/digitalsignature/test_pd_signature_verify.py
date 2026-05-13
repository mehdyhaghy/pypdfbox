"""Wave 1303 hand-written tests for :meth:`PDSignature.verify`.

These tests round-trip a synthetic PKCS#7-signed PDF skeleton through
:class:`Pkcs7Signature` and exercise the three contract points that
production callers care about:

1. **Round-trip**: a freshly signed document verifies cleanly
   (``is_valid=True``, ``errors=[]``).
2. **Tamper outside /ByteRange**: flipping a byte that lies inside the
   ``/Contents`` placeholder window — i.e. *not* covered by the digest —
   must STILL verify, because the spec deliberately excises that window
   from the hash.
3. **Tamper inside /ByteRange**: flipping a byte covered by the digest
   must FAIL verification with a digest-mismatch diagnostic.

The certs are self-signed inline so the suite stays offline. We don't
use ``protect(StandardProtectionPolicy)`` here — that's the *encryption*
pipeline; PDF signing is a separate concern wired through
:class:`Pkcs7Signature` and a manually constructed ``/Contents``
placeholder. The wave brief mentioned ``protect`` but the underlying
intent was "build a signed PDF in-process with a self-signed cert",
which the signature builder does directly.
"""

from __future__ import annotations

import datetime
import io

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSignature,
    Pkcs7Signature,
    compute_byte_range,
)

# ---------- in-process cert + signed-document fixtures ----------


def _make_self_signed_cert(
    common_name: str = "pypdfbox-test-signer",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    """Mint a self-signed RSA-2048 cert valid for one day.

    Mirrors the pattern used by the wave 1286 tests; kept local here so
    this file doesn't import private helpers from sibling test modules.
    """
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, common_name)]
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=None), critical=True
        )
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _build_signed_document(
    cert: x509.Certificate,
    key: rsa.RSAPrivateKey,
) -> tuple[bytes, list[int], int, int, int]:
    """Return ``(document_bytes, /ByteRange, prefix_len, splice_open, splice_close)``.

    ``splice_open`` is the index of the leading ``<`` of the /Contents
    hex placeholder; ``splice_close`` is the index of the trailing ``>``.
    Returning both lets callers tamper either inside the placeholder
    (``splice_open < idx < splice_close``) or in the covered range
    (``idx < splice_open`` or ``idx > splice_close``).
    """
    prefix = b"%PDF-1.7\n" + b"A" * 64  # part of /ByteRange range 1
    suffix = b"B" * 64 + b"\n%%EOF\n"  # part of /ByteRange range 2
    placeholder = b"\x00" * 4096  # placeholder for /Contents
    document_template = prefix + b"<" + placeholder + b">" + suffix
    splice_open = len(prefix)
    splice_close = splice_open + 1 + len(placeholder)
    byte_range = compute_byte_range(
        document_template, splice_open, splice_close
    )
    bracketed = (
        document_template[byte_range[0] : byte_range[0] + byte_range[1]]
        + document_template[byte_range[2] : byte_range[2] + byte_range[3]]
    )
    blob = Pkcs7Signature(cert, key).sign(io.BytesIO(bracketed))
    splice = blob + b"\x00" * (len(placeholder) - len(blob))
    document = prefix + b"<" + splice + b">" + suffix
    # The splice itself starts at splice_open + 1 (past the leading `<`).
    return document, byte_range, len(prefix), splice_open, splice_close


def _make_signature_dict(
    byte_range: list[int], splice: bytes
) -> PDSignature:
    """Wire a :class:`PDSignature` with the SubFilter, /ByteRange and
    /Contents that :meth:`verify` consumes."""
    sig = PDSignature()
    sig.set_sub_filter("adbe.pkcs7.detached")
    sig.set_byte_range(byte_range)
    sig.set_contents(splice)
    return sig


# ---------- 1. round-trip ----------


def test_verify_round_trip_signed_document_passes() -> None:
    """A freshly signed synthetic PDF skeleton round-trips through
    :meth:`PDSignature.verify` with ``is_valid=True``."""
    cert, key = _make_self_signed_cert()
    document, byte_range, _prefix_len, splice_open, splice_close = (
        _build_signed_document(cert, key)
    )
    splice = document[splice_open + 1 : splice_close]
    sig = _make_signature_dict(byte_range, splice)

    result = sig.verify(document)
    assert result.is_valid is True, result.errors
    assert not result.errors
    # Signer cert was recovered and exposed via convenience accessors.
    assert result.signer_certificate is not None
    assert result.has_signer()
    assert "pypdfbox-test-signer" in (result.signer_subject or "")
    # Both digests landed and matched.
    assert result.has_signed_digest()
    assert result.has_computed_digest()
    assert result.digest_matches()


# ---------- 2. tamper OUTSIDE /ByteRange (inside /Contents window) ----------


def test_verify_tampering_inside_contents_placeholder_still_passes() -> None:
    """Flipping a byte that lies inside the /Contents <...> window but
    NOT inside the signature blob — i.e. inside the NUL padding tail —
    leaves the digest intact (range is excised) AND leaves the PKCS#7
    parser happy (it ``rstrip(b"\\x00")``s the placeholder), so verify
    must still pass."""
    cert, key = _make_self_signed_cert()
    document, byte_range, _prefix_len, splice_open, splice_close = (
        _build_signed_document(cert, key)
    )
    splice = bytearray(document[splice_open + 1 : splice_close])

    # Find the first NUL-pad byte at the end of the real PKCS#7 blob.
    pkcs7_end = len(splice.rstrip(b"\x00"))
    assert pkcs7_end < len(splice), (
        "test fixture must leave NUL padding inside the placeholder; "
        f"got pkcs7_end={pkcs7_end} placeholder_len={len(splice)}"
    )
    # Flip a byte well inside the padding tail (after the DER blob).
    tamper_idx_in_splice = pkcs7_end + 64
    splice[tamper_idx_in_splice] ^= 0xFF

    # Rebuild the document so the tampered byte is in place. The
    # tampered byte sits at absolute index splice_open + 1 +
    # tamper_idx_in_splice — which is between splice_open and
    # splice_close, hence OUTSIDE both /ByteRange slices.
    tampered_doc = (
        document[: splice_open + 1]
        + bytes(splice)
        + document[splice_close:]
    )
    absolute_tamper_idx = splice_open + 1 + tamper_idx_in_splice
    assert splice_open < absolute_tamper_idx < splice_close, (
        "tamper index must sit inside the /Contents placeholder window"
    )

    sig = _make_signature_dict(byte_range, bytes(splice))
    result = sig.verify(tampered_doc)
    assert result.is_valid is True, result.errors
    assert not result.errors


# ---------- 3. tamper INSIDE /ByteRange ----------


def test_verify_tampering_inside_byte_range_fails() -> None:
    """Flipping a byte inside the signed range produces a digest
    mismatch — :meth:`verify` must return ``is_valid=False`` with a
    diagnostic mentioning the digest."""
    cert, key = _make_self_signed_cert()
    document, byte_range, prefix_len, splice_open, splice_close = (
        _build_signed_document(cert, key)
    )
    splice = document[splice_open + 1 : splice_close]

    # Flip a byte in the prefix `A`-fill (range 1, covered by the digest).
    # Pick prefix_len // 2 to land squarely inside range 1.
    tamper_idx = max(1, prefix_len // 2)
    assert 0 <= tamper_idx < splice_open  # inside range 1 by construction
    tampered = bytearray(document)
    tampered[tamper_idx] ^= 0x55

    sig = _make_signature_dict(byte_range, splice)
    result = sig.verify(bytes(tampered))
    assert result.is_valid is False
    assert result.errors
    # The recovered signed digest and the freshly recomputed digest
    # must both be present so the failure is a *mismatch*, not a
    # *missing-digest* error.
    assert result.has_signed_digest()
    assert result.has_computed_digest()
    assert not result.digest_matches()
    assert any("digest" in err.lower() for err in result.errors)


def test_verify_tampering_inside_second_byte_range_slice_fails() -> None:
    """Same as the prefix-side test but tamper a byte in the *suffix*
    half (range 2 of /ByteRange) — both slices must be covered."""
    cert, key = _make_self_signed_cert()
    document, byte_range, _prefix_len, _splice_open, splice_close = (
        _build_signed_document(cert, key)
    )
    splice = document[_splice_open + 1 : splice_close]

    # Flip a byte in the suffix region (after `>`, inside range 2).
    tamper_idx = splice_close + 5
    assert tamper_idx < len(document)
    tampered = bytearray(document)
    tampered[tamper_idx] ^= 0xA5

    sig = _make_signature_dict(byte_range, splice)
    result = sig.verify(bytes(tampered))
    assert result.is_valid is False
    assert result.errors
    assert not result.digest_matches()
