"""Tests for the write-side signature pipeline.

Covers :meth:`PDDocument.add_signature`,
:meth:`PDDocument.save_incremental_for_external_signing`, and the
:class:`Pkcs7Signature` driver.
"""

from __future__ import annotations

import datetime
import io
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDSignature,
    Pkcs7Signature,
    SignatureInterface,
)
from pypdfbox.pdmodel.pd_document import ExternalSigningSupport

# ---------- helpers ----------


def _make_self_signed_cert() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-test"),
            x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox signing test"),
        ]
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _build_tiny_pdf(path: Path) -> Path:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(path)
    finally:
        doc.close()
    return path


# ---------- happy-path Pkcs7Signature ----------


def test_pkcs7_signature_round_trip(tmp_path: Path) -> None:
    cert, key = _make_self_signed_cert()
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out = tmp_path / "signed.pdf"

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_name("Alice")
        sig.set_reason("test")
        signer = Pkcs7Signature(cert, key)
        doc.add_signature(sig, signer)
        doc.save_incremental(out)

    data = out.read_bytes()
    # File must start with the original header (incremental preserves bytes).
    assert data.startswith(b"%PDF-")

    # /Contents must be present, hex-encoded, non-zero PKCS#7 blob.
    with PDDocument.load(out) as reloaded:
        from pypdfbox.cos import COSDictionary, COSName

        catalog = reloaded.get_document_catalog()
        acro = catalog.get_acro_form()
        assert acro is not None
        fields = acro.get_fields()
        assert len(fields) == 1
        sig_dict = (
            fields[0].get_cos_object().get_dictionary_object(COSName.get_pdf_name("V"))
        )
        assert isinstance(sig_dict, COSDictionary)
        loaded_sig = PDSignature(sig_dict)
        contents = loaded_sig.get_contents()
        assert contents is not None and len(contents) > 0
        # Trim trailing zero padding then ensure parses as PKCS#7 DER.
        trimmed = contents.rstrip(b"\x00")
        certs = pkcs7.load_der_pkcs7_certificates(trimmed)
        assert len(certs) >= 1
        assert certs[0].subject == cert.subject

        # /ByteRange validation: bracketing math must equal file size.
        br = loaded_sig.get_byte_range()
        assert br is not None and len(br) == 4
        start1, len1, start2, len2 = br
        assert start1 == 0
        # Round-trip the bracketed bytes — they must hash deterministically.
        bracketed = data[start1 : start1 + len1] + data[start2 : start2 + len2]
        # The bracketed bytes BORDER the /Contents placeholder (the bracketed
        # ranges include the angle brackets `<` and `>` at the boundaries —
        # ISO 32000-1 §12.8.1: only the hex chars between < and > are skipped).
        assert data[start1 + len1 - 1 : start1 + len1] == b"<"
        assert data[start2 : start2 + 1] == b">"
        # Skipped region = the hex-encoded /Contents body (no brackets).
        skipped = data[start1 + len1 : start2]
        assert all(c in b"0123456789ABCDEFabcdef" for c in skipped)
        # And bracketed length matches expectation.
        assert len(bracketed) == len(data) - len(skipped)


# ---------- external signing variant ----------


def test_external_signing_round_trip(tmp_path: Path) -> None:
    cert, key = _make_self_signed_cert()
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out = tmp_path / "external.pdf"

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_name("Bob")
        # No SignatureInterface — we'll sign externally.
        doc.add_signature(sig)
        with open(out, "wb") as fh:
            handle = doc.save_incremental_for_external_signing(fh)
            assert isinstance(handle, ExternalSigningSupport)
            content = handle.get_content()
            assert isinstance(content, bytes) and len(content) > 0

            # Caller drives the signing themselves.
            external_signer = Pkcs7Signature(cert, key)
            blob = external_signer.sign(io.BytesIO(content))
            handle.set_signature(blob)

    # Output file must exist and be non-empty.
    assert out.stat().st_size > 0

    with PDDocument.load(out) as reloaded:
        from pypdfbox.cos import COSDictionary, COSName

        acro = reloaded.get_document_catalog().get_acro_form()
        assert acro is not None
        fields = acro.get_fields()
        assert len(fields) == 1
        sig_dict = (
            fields[0].get_cos_object().get_dictionary_object(COSName.get_pdf_name("V"))
        )
        assert isinstance(sig_dict, COSDictionary)
        loaded = PDSignature(sig_dict)
        contents = loaded.get_contents()
        assert contents is not None
        trimmed = contents.rstrip(b"\x00")
        certs = pkcs7.load_der_pkcs7_certificates(trimmed)
        assert len(certs) >= 1


# ---------- splice math (mocked signer) ----------


class _DummySigner(SignatureInterface):
    """Returns a fixed PKCS#7-shaped blob — used to assert the splicing
    math doesn't depend on real PKCS#7 ASN.1."""

    def __init__(self, blob: bytes) -> None:
        self._blob = blob
        self.received: bytes | None = None

    def sign(self, content: io.BytesIO) -> bytes:  # type: ignore[override]
        self.received = content.read()
        return self._blob


def test_splice_byte_range_arithmetic(tmp_path: Path) -> None:
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out = tmp_path / "spliced.pdf"

    blob = b"\x30\x80" + b"\xab" * 510  # 512 byte fake DER
    signer = _DummySigner(blob)

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        doc.add_signature(sig, signer)
        doc.save_incremental(out)

    data = out.read_bytes()
    with PDDocument.load(out) as reloaded:
        from pypdfbox.cos import COSDictionary, COSName

        acro = reloaded.get_document_catalog().get_acro_form()
        assert acro is not None
        sig_dict = (
            acro.get_fields()[0]
            .get_cos_object()
            .get_dictionary_object(COSName.get_pdf_name("V"))
        )
        assert isinstance(sig_dict, COSDictionary)
        loaded = PDSignature(sig_dict)
        br = loaded.get_byte_range()
        assert br is not None
        start1, len1, start2, len2 = br
        # ByteRange ranges include the surrounding angle brackets — only the
        # 16384 hex chars BETWEEN < and > are skipped.
        skipped = start2 - (start1 + len1)
        assert skipped == 16384

        # Sum of bracketed bytes + skipped region must equal file length.
        assert len1 + len2 + skipped == len(data)
        # First range starts at 0.
        assert start1 == 0
        # Second range ends exactly at EOF.
        assert start2 + len2 == len(data)
        # Boundary bytes = the < and > delimiters themselves.
        assert data[start1 + len1 - 1 : start1 + len1] == b"<"
        assert data[start2 : start2 + 1] == b">"

        # Confirm what the signer received was the actual concatenated slices.
        bracketed = data[start1 : start1 + len1] + data[start2 : start2 + len2]
        assert signer.received == bracketed

        # /Contents must contain our blob in hex (followed by zero padding).
        contents = loaded.get_contents()
        assert contents is not None
        assert contents[: len(blob)] == blob
        # Padding bytes are all zero.
        assert all(b == 0 for b in contents[len(blob) :])


def test_splice_rejects_oversize_blob(tmp_path: Path) -> None:
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out = tmp_path / "should-fail.pdf"

    # Blob larger than the placeholder (16384 hex chars = 8192 raw bytes).
    huge = b"\xff" * 9000
    signer = _DummySigner(huge)

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        doc.add_signature(sig, signer)
        with pytest.raises(ValueError, match="larger than reserved"):
            doc.save_incremental(out)


def test_add_signature_requires_pdsignature(tmp_path: Path) -> None:
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    with PDDocument.load(src) as doc, pytest.raises(TypeError, match="PDSignature"):
        doc.add_signature("not a signature")  # type: ignore[arg-type]


def test_save_incremental_without_interface_after_add_signature_errors(
    tmp_path: Path,
) -> None:
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out = tmp_path / "noop.pdf"
    with PDDocument.load(src) as doc:
        sig = PDSignature()
        doc.add_signature(sig)  # no SignatureInterface
        with pytest.raises(ValueError, match="SignatureInterface"):
            doc.save_incremental(out)


def test_external_signing_requires_prior_add_signature(tmp_path: Path) -> None:
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out_path = tmp_path / "x.pdf"
    with (
        PDDocument.load(src) as doc,
        open(out_path, "wb") as fh,
        pytest.raises(ValueError, match="add_signature"),
    ):
        doc.save_incremental_for_external_signing(fh)


def test_pkcs7_signature_produces_valid_der() -> None:
    """Standalone Pkcs7Signature smoke — no PDF involved."""
    cert, key = _make_self_signed_cert()
    signer = Pkcs7Signature(cert, key)
    blob = signer.sign(io.BytesIO(b"hello world"))
    assert isinstance(blob, bytes) and len(blob) > 0
    certs = pkcs7.load_der_pkcs7_certificates(blob)
    assert len(certs) == 1
    assert certs[0].subject == cert.subject


def test_signature_interface_is_abstract() -> None:
    with pytest.raises(TypeError):
        SignatureInterface()  # type: ignore[abstract]


def test_pdsignature_verify_extracts_certificate_after_sign(tmp_path: Path) -> None:
    """End-to-end: sign a doc, then call PDSignature.verify on the result —
    even though full chain validation is deferred, the cert must extract."""
    cert, key = _make_self_signed_cert()
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    out = tmp_path / "signed.pdf"

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        doc.add_signature(sig, Pkcs7Signature(cert, key))
        doc.save_incremental(out)

    data = out.read_bytes()
    with PDDocument.load(out) as reloaded:
        from pypdfbox.cos import COSDictionary, COSName

        acro = reloaded.get_document_catalog().get_acro_form()
        sig_dict = (
            acro.get_fields()[0]
            .get_cos_object()
            .get_dictionary_object(COSName.get_pdf_name("V"))
        )
        assert isinstance(sig_dict, COSDictionary)
        loaded = PDSignature(sig_dict)

        # Strip trailing zero padding from /Contents before verify reads it.
        # PDSignature.verify hands /Contents straight to PKCS#7 parsing,
        # which does NOT tolerate zero-pad. Replace /Contents with trimmed
        # bytes for the verify call.
        contents = loaded.get_contents()
        assert contents is not None
        trimmed = contents.rstrip(b"\x00")
        loaded.set_contents(trimmed)

        result = loaded.verify(data)
        # Best-effort verify: full chain validation deferred → not is_valid,
        # but signer cert must come back.
        assert result.signer_certificate is not None
        assert result.signer_subject is not None
