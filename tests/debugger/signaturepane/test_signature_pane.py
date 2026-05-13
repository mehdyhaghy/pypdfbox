"""Tests for :class:`SignaturePane`."""

from __future__ import annotations

import datetime as _datetime

import pytest

from pypdfbox.cos import COSString
from pypdfbox.debugger.signaturepane.signature_pane import (
    SignaturePane,
    hex_dump,
    parse_pkcs7_certificates,
)

# Lazy-load cryptography for PKCS#7 round-tripping. Skip on absence rather
# than ImportError-on-test-collection to keep the rest of the file useful.
crypto = pytest.importorskip("cryptography")


def _make_pkcs7_blob() -> bytes:
    """Build a tiny PKCS#7 SignedData blob carrying one self-signed cert.

    We use PyCA's high-level pkcs7 builder; this produces a detached
    SignedData identical to what a PDF signer would write into
    ``/Contents``.
    """
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs7
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, "pypdfbox-test"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox"),
        ]
    )
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(_datetime.datetime(2026, 1, 1, tzinfo=_datetime.UTC))
        .not_valid_after(_datetime.datetime(2027, 1, 1, tzinfo=_datetime.UTC))
        .sign(key, hashes.SHA256())
    )
    builder = pkcs7.PKCS7SignatureBuilder().set_data(b"hello world")
    builder = builder.add_signer(cert, key, hashes.SHA256())
    return builder.sign(
        serialization.Encoding.DER,
        [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
    )


def test_hex_dump_formats_offsets_and_bytes() -> None:
    dump = hex_dump(b"\x00\x01\x02\x03\xff", columns=4)
    lines = dump.splitlines()
    assert lines[0].startswith("00000000")
    assert "0001" in lines[0]


def test_hex_dump_handles_empty_input() -> None:
    assert hex_dump(b"") == ""


def test_parse_pkcs7_certificates_extracts_subject() -> None:
    blob = _make_pkcs7_blob()
    summaries = parse_pkcs7_certificates(blob)
    assert summaries
    assert "pypdfbox-test" in summaries[0].subject
    assert "pypdfbox-test" in summaries[0].issuer


def test_parse_pkcs7_certificates_handles_invalid_input() -> None:
    summaries = parse_pkcs7_certificates(b"not really a PKCS#7 blob")
    assert summaries
    assert summaries[0].errors


def test_parse_pkcs7_certificates_strips_trailing_nul_padding() -> None:
    blob = _make_pkcs7_blob() + b"\x00" * 64
    summaries = parse_pkcs7_certificates(blob)
    assert "pypdfbox-test" in summaries[0].subject


def test_signature_pane_creates_two_tabs(tk_root) -> None:
    blob = _make_pkcs7_blob()
    cos = COSString(blob)
    pane = SignaturePane(tk_root, cos)
    assert len(pane.get_pane().tabs()) == 2


def test_signature_pane_cert_tree_lists_embedded_certificate(tk_root) -> None:
    blob = _make_pkcs7_blob()
    cos = COSString(blob)
    pane = SignaturePane(tk_root, cos)
    tree = pane.cert_tree
    children = tree.get_children()
    assert len(children) == 1
    item = tree.item(children[0])
    assert "pypdfbox-test" in item["text"]


def test_signature_pane_asn1_tab_contains_hex_dump(tk_root) -> None:
    blob = _make_pkcs7_blob()
    cos = COSString(blob)
    pane = SignaturePane(tk_root, cos)
    body = pane.asn1_text.get("1.0", "end-1c")
    # Hex dump format always starts with the first offset line.
    assert body.startswith("00000000")


# ---- _utc_string + summary error paths -----------------------------------


def test_utc_string_for_datetime() -> None:
    from pypdfbox.debugger.signaturepane.signature_pane import _utc_string

    dt = _datetime.datetime(2026, 5, 12, 10, 30, tzinfo=_datetime.UTC)
    assert _utc_string(dt).startswith("2026-05-12")


def test_utc_string_for_none() -> None:
    from pypdfbox.debugger.signaturepane.signature_pane import _utc_string

    assert _utc_string(None) == ""


def test_utc_string_for_non_datetime_value() -> None:
    from pypdfbox.debugger.signaturepane.signature_pane import _utc_string

    # A bare string falls into the ``str(value)`` branch.
    assert _utc_string("2026-05-12") == "2026-05-12"


def test_parse_pkcs7_swallows_subject_attribute_errors() -> None:
    """A cert object whose attribute accessors raise should yield a
    ``_CertSummary`` whose ``errors`` list captures every failure.

    We monkey-patch ``pkcs7.load_der_pkcs7_certificates`` so we can hand
    in a faux cert that throws on every accessor; this exercises the
    per-attribute error paths.
    """
    from cryptography.hazmat.primitives.serialization import pkcs7

    from pypdfbox.debugger.signaturepane import signature_pane

    class _BadCert:
        @property
        def subject(self) -> None:
            raise RuntimeError("subject boom")

        @property
        def issuer(self) -> None:
            raise RuntimeError("issuer boom")

        @property
        def serial_number(self) -> int:
            raise RuntimeError("serial boom")

        @property
        def not_valid_before(self) -> None:
            raise RuntimeError("validity boom")

        @property
        def not_valid_after(self) -> None:
            raise RuntimeError("validity boom")

    original = pkcs7.load_der_pkcs7_certificates
    pkcs7.load_der_pkcs7_certificates = lambda _blob: [_BadCert()]
    try:
        summaries = signature_pane.parse_pkcs7_certificates(b"unused")
    finally:
        pkcs7.load_der_pkcs7_certificates = original
    assert len(summaries) == 1
    errors = summaries[0].errors
    # subject, issuer, serial, validity all surfaced an error.
    assert any("subject" in e for e in errors)
    assert any("issuer" in e for e in errors)
    assert any("serial" in e for e in errors)
    assert any("validity" in e for e in errors)


def test_signature_pane_inserts_summary_errors_into_cert_tree(tk_root) -> None:
    """When a cert summary carries error entries, they appear as
    children under the certificate row in the tree."""
    from pypdfbox.cos import COSString
    from pypdfbox.debugger.signaturepane import signature_pane

    # Pre-populate parse to return one summary with two errors.
    fake = signature_pane._CertSummary()
    fake.subject = "CN=test"
    fake.errors.append("attribute1: oops")
    fake.errors.append("attribute2: oops")

    original = signature_pane.parse_pkcs7_certificates
    signature_pane.parse_pkcs7_certificates = lambda _blob: [fake]
    try:
        pane = SignaturePane(tk_root, COSString(b"unused"))
    finally:
        signature_pane.parse_pkcs7_certificates = original
    children = pane.cert_tree.get_children()
    assert len(children) == 1
    grand_children = pane.cert_tree.get_children(children[0])
    assert len(grand_children) == 2
