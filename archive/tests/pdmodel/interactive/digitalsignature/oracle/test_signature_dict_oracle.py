"""Live Apache PDFBox differential parity for signature-dictionary STRUCTURE.

Companion to ``test_byte_range_oracle.py`` (which pins the /ByteRange byte-offset
arithmetic). This module pins the *dictionary identity* of an externally-signed
signature value dict: the /Type, /Filter, /SubFilter name fields and the reserved
/Contents placeholder size.

Direction: **pypdfbox-writes → Java-reads**. pypdfbox builds a 1-page PDF, adds a
:class:`PDSignature` (taking the engine defaults for /Filter + /SubFilter), and
drives :meth:`PDDocument.save_incremental_for_external_signing` →
:meth:`ExternalSigningSupport.set_signature`. ``SignatureDictProbe`` then loads
the result with Apache PDFBox 3.0.7 and reports the dict fields exactly as PDFBox
parses them.

We assert PDFBox reads back:
  1. /Type    -> ``Sig``
  2. /Filter  -> ``Adobe.PPKLite``   (PDFBox default; matches pypdfbox default)
  3. /SubFilter -> ``adbe.pkcs7.detached``
  4. /Contents decoded length == pypdfbox's reserved placeholder size
     (``_CONTENTS_PLACEHOLDER_HEX_LEN // 2`` raw bytes), and == what pypdfbox's
     own :meth:`PDSignature.get_contents` reads from the same file.

No key/cert material is committed; the PKCS#7 blob is produced in-test with a
self-signed cert built via ``cryptography``.
"""

from __future__ import annotations

import datetime
import io
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from pypdfbox.pdmodel import PDDocument, PDPage, PDResources
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature, Pkcs7Signature
from tests.oracle.harness import requires_oracle, run_probe_text


def _parse_probe_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _make_self_signed_cert(
    cn: str = "pypdfbox-sigdict-signer",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-sigdict-oracle"),
            x509.NameAttribute(NameOID.COMMON_NAME, cn),
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


def _build_unsigned_pdf(out: Path) -> None:
    doc = PDDocument()
    try:
        page = PDPage()
        page.set_resources(PDResources())
        doc.add_page(page)
        doc.save(out)
    finally:
        doc.close()


def _sign_external_with_defaults(src: Path, out: Path) -> None:
    """Sign ``src`` via the external-signing path, taking the engine defaults
    for /Filter and /SubFilter (only /Name is set explicitly)."""
    cert, key = _make_self_signed_cert()
    signer = Pkcs7Signature(cert, key)
    with PDDocument.load(src) as doc:
        sig = PDSignature()
        # Deliberately do NOT set /Filter or /SubFilter — exercise the engine
        # defaults so the probe verifies them, not the caller's choice.
        sig.set_name("pypdfbox sigdict signer")
        doc.add_signature(sig, signer)
        with open(out, "wb") as fh:
            handle = doc.save_incremental_for_external_signing(fh)
            content = handle.get_content()
            pkcs7 = signer.sign(io.BytesIO(content))
            handle.set_signature(pkcs7)


# --------------------------------------------------------- the parity tests


@requires_oracle
def test_type_filter_subfilter_match_pdfbox(tmp_path: Path) -> None:
    """PDFBox reads back the spec-mandated /Type /Sig plus the engine-default
    /Filter (Adobe.PPKLite) and /SubFilter (adbe.pkcs7.detached) names."""
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)
    _sign_external_with_defaults(unsigned, signed)

    java = _parse_probe_kv(run_probe_text("SignatureDictProbe", str(signed)))
    assert java["count"] == "1"
    assert java["sig.0.type"] == "Sig"
    assert java["sig.0.filter"] == PDSignature.FILTER_ADOBE_PPKLITE
    assert java["sig.0.subfilter"] == PDSignature.SUBFILTER_ADBE_PKCS7_DETACHED
    assert java["sig.0.name"] == "pypdfbox sigdict signer"


@requires_oracle
def test_contents_placeholder_size_matches_pdfbox(tmp_path: Path) -> None:
    """PDFBox decodes the /Contents hex placeholder to exactly the raw byte
    count pypdfbox reserved (``_CONTENTS_PLACEHOLDER_HEX_LEN // 2``), and
    pypdfbox's own get_contents reads the same length from the same bytes."""
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)
    _sign_external_with_defaults(unsigned, signed)

    reserved_raw = PDDocument._CONTENTS_PLACEHOLDER_HEX_LEN // 2

    java = _parse_probe_kv(run_probe_text("SignatureDictProbe", str(signed)))
    assert int(java["sig.0.contentsLen"]) == reserved_raw

    # pypdfbox-side read-back agrees with PDFBox: parse the signed file and
    # read the same /Contents placeholder length.
    with PDDocument.load(signed) as doc:
        sigs = doc.get_signature_dictionaries()
        assert len(sigs) == 1
        contents = sigs[0].get_contents()
        assert contents is not None
        assert len(contents) == reserved_raw


@requires_oracle
def test_explicit_filter_subfilter_round_trip(tmp_path: Path) -> None:
    """When the caller sets /Filter + /SubFilter explicitly, PDFBox reads back
    exactly those names (no engine override)."""
    cert, key = _make_self_signed_cert()
    signer = Pkcs7Signature(cert, key)
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)

    with PDDocument.load(unsigned) as doc:
        sig = PDSignature()
        sig.set_filter(PDSignature.FILTER_ADOBE_PPKLITE)
        sig.set_sub_filter(PDSignature.SUBFILTER_ETSI_CADES_DETACHED)
        sig.set_name("explicit subfilter signer")
        doc.add_signature(sig, signer)
        with open(signed, "wb") as fh:
            handle = doc.save_incremental_for_external_signing(fh)
            pkcs7 = signer.sign(io.BytesIO(handle.get_content()))
            handle.set_signature(pkcs7)

    java = _parse_probe_kv(run_probe_text("SignatureDictProbe", str(signed)))
    assert java["sig.0.type"] == "Sig"
    assert java["sig.0.filter"] == PDSignature.FILTER_ADOBE_PPKLITE
    assert java["sig.0.subfilter"] == PDSignature.SUBFILTER_ETSI_CADES_DETACHED


@requires_oracle
def test_identity_fields_round_trip(tmp_path: Path) -> None:
    """PDFBox reads back the /Name, /Reason, /Location, /ContactInfo identity
    strings pypdfbox wrote, and sees the /ByteRange emitted inline (direct) —
    the upstream PDSignature.setByteRange contract (ary.setDirect(true))."""
    cert, key = _make_self_signed_cert()
    signer = Pkcs7Signature(cert, key)
    unsigned = tmp_path / "unsigned.pdf"
    signed = tmp_path / "signed.pdf"
    _build_unsigned_pdf(unsigned)

    with PDDocument.load(unsigned) as doc:
        sig = PDSignature()
        sig.set_name("Identity Signer")
        sig.set_reason("I approve this document")
        sig.set_location("Berlin, DE")
        sig.set_contact_info("signer@example.test")
        doc.add_signature(sig, signer)
        with open(signed, "wb") as fh:
            handle = doc.save_incremental_for_external_signing(fh)
            pkcs7 = signer.sign(io.BytesIO(handle.get_content()))
            handle.set_signature(pkcs7)

    java = _parse_probe_kv(run_probe_text("SignatureDictProbe", str(signed)))
    assert java["sig.0.name"] == "Identity Signer"
    assert java["sig.0.reason"] == "I approve this document"
    assert java["sig.0.location"] == "Berlin, DE"
    assert java["sig.0.contactInfo"] == "signer@example.test"
    assert java["sig.0.byteRangeIsDirect"] == "true"

    # pypdfbox-side read-back agrees field-for-field.
    with PDDocument.load(signed) as doc:
        loaded = doc.get_signature_dictionaries()[0]
        assert loaded.get_name() == "Identity Signer"
        assert loaded.get_reason() == "I approve this document"
        assert loaded.get_location() == "Berlin, DE"
        assert loaded.get_contact_info() == "signer@example.test"
