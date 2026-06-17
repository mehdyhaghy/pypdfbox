"""Live cross-library differential parity for PAdES-LTV /DSS + /VRI bundling.

Direction: **pypdfbox-writes → Java-reads**. pypdfbox signs a PDF, then adds
a PAdES-LTV Document Security Store (PDF 32000-2 §12.8.4) via
:class:`PDDocumentSecurityStore` — document-wide ``/Certs`` / ``/CRLs`` /
``/OCSPs`` pools plus a per-signature ``/VRI`` entry keyed on the uppercase
hex SHA-1 of the signature's ``/Contents`` octet string. The revocation
evidence (a CRL and an OCSP response) is synthesised in-test with
``cryptography`` so the suite stays offline; no key/cert/CRL material is
committed.

``DssReadProbe`` then loads the LTV PDF with Apache PDFBox 3.0.7 and walks the
``/DSS`` COS dictionary directly (PDFBox 3.0.7 ships no high-level
PDDocumentSecurityStore), emitting:

* document-wide ``/Certs`` / ``/CRLs`` / ``/OCSPs`` counts,
* the ``/VRI`` key set and each entry's ``/Cert`` / ``/CRL`` / ``/OCSP``
  counts,
* and — for each signature — the VRI key PDFBox derives from ``/Contents``
  plus whether the detached CMS still verifies over the bracketed
  ``/ByteRange`` (digest intact).

We assert PDFBox reads back exactly the structure pypdfbox wrote, that the
VRI key derivation agrees between both libraries, and that the original
signature is still intact after the LTV incremental append — i.e. the
``/DSS`` revision was appended past the signed byte range, not overlaid on it.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509.oid import NameOID

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.examples.signature.cert import (
    build_synthetic_crl,
    build_synthetic_ocsp_response,
    collect_revocation_info,
)
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDDocumentSecurityStore,
    PDSignature,
    Pkcs7Signature,
)
from tests.oracle.harness import requires_oracle, run_probe_text

_V = COSName.get_pdf_name("V")


# --------------------------------------------------------------- helpers


def _parse_probe_kv(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if "=" in line:
            key, _, value = line.partition("=")
            out[key] = value
    return out


def _make_self_signed_cert(
    cn: str,
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-ltv-oracle"),
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


def _build_signed_pdf(
    tmp_path: Path, cn: str = "pypdfbox-ltv-signer"
) -> tuple[Path, x509.Certificate, rsa.RSAPrivateKey]:
    """Build a 1-page PDF and sign it with a fresh self-signed cert."""
    cert, key = _make_self_signed_cert(cn)
    src = tmp_path / "in.pdf"
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(src)
    finally:
        doc.close()

    signed = tmp_path / "signed.pdf"
    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_name("LTV signer")
        sig.set_reason("DSS/VRI LTV oracle parity")
        doc.add_signature(sig, Pkcs7Signature(cert, key))
        doc.save_incremental(signed)
    return signed, cert, key


def _signature_from_acroform(doc: PDDocument) -> PDSignature:
    acro = doc.get_document_catalog().get_acro_form()
    assert acro is not None
    fields = acro.get_fields()
    assert len(fields) >= 1
    sig_dict = fields[0].get_cos_object().get_dictionary_object(_V)
    assert isinstance(sig_dict, COSDictionary)
    return PDSignature(sig_dict)


def _add_ltv_dss(
    signed: Path,
    out: Path,
    cert: x509.Certificate,
    key: rsa.RSAPrivateKey,
    *,
    with_vri: bool = True,
) -> str:
    """Reload ``signed``, bundle /DSS (+/VRI), incrementally save to ``out``.

    Returns the expected VRI key (uppercase SHA-1 hex of /Contents).
    """
    crl = build_synthetic_crl(issuer_cert=cert, issuer_key=key)
    ocsp_resp = build_synthetic_ocsp_response(
        subject_cert=cert,
        issuer_cert=cert,
        responder_cert=cert,
        responder_key=key,
    )
    bundle = collect_revocation_info(
        cert,
        intermediate_certs=[],
        issuer_cert=None,
        crls=[crl],
        ocsp_responses=[ocsp_resp],
    )

    with PDDocument.load(signed) as doc:
        sig = _signature_from_acroform(doc)
        contents = sig.get_contents()
        assert contents is not None
        expected_key = hashlib.sha1(contents).hexdigest().upper()  # noqa: S324

        dss = PDDocumentSecurityStore.ensure_on(doc)
        dss.bundle(
            certs=bundle.certs,
            crls=bundle.crls,
            ocsps=bundle.ocsps,
            signature=sig if with_vri else None,
        )
        doc.save_incremental(out)
    return expected_key


# --------------------------------------------------------- the parity tests


@requires_oracle
def test_pypdfbox_dss_vri_read_back_by_pdfbox(tmp_path: Path) -> None:
    """pypdfbox writes /DSS + per-signature /VRI; PDFBox reads back the same
    pool counts, the same VRI key set, and the same per-VRI counts."""
    signed, cert, key = _build_signed_pdf(tmp_path)
    out = tmp_path / "ltv.pdf"
    expected_key = _add_ltv_dss(signed, out, cert, key)

    java = _parse_probe_kv(run_probe_text("DssReadProbe", str(out)))

    # /DSS is present and typed.
    assert java["dss.present"] == "true"
    assert java["dss.type"] == "DSS"

    # Document-wide pools: 1 cert + 1 CRL + 1 OCSP.
    assert java["dss.certs"] == "1"
    assert java["dss.crls"] == "1"
    assert java["dss.ocsps"] == "1"

    # /VRI present and keyed exactly on the signature's /Contents SHA-1.
    assert java["dss.vri.present"] == "true"
    assert java["dss.vri.keys"] == expected_key

    # The per-signature VRI entry mirrors the pools.
    assert java[f"vri.{expected_key}.cert"] == "1"
    assert java[f"vri.{expected_key}.crl"] == "1"
    assert java[f"vri.{expected_key}.ocsp"] == "1"
    # PDFBox's own SHA-1(/Contents) lands on this key — cross-lib agreement
    # on the VRI key derivation, not just on the bytes we happened to write.
    assert java[f"vri.{expected_key}.matchesSig"] == "true"


@requires_oracle
def test_pypdfbox_vri_key_matches_pdfbox_contents_sha1(tmp_path: Path) -> None:
    """The /VRI key pypdfbox computed equals the uppercase SHA-1 hex of the
    /Contents octet string that PDFBox itself reads from the signature — the
    high-value PAdES-LTV correctness check."""
    signed, cert, key = _build_signed_pdf(tmp_path)
    out = tmp_path / "ltv_key.pdf"
    expected_key = _add_ltv_dss(signed, out, cert, key)

    java = _parse_probe_kv(run_probe_text("DssReadProbe", str(out)))
    assert java["sig.count"] == "1"
    # PDFBox-derived key from the /Contents it parsed back == pypdfbox's key.
    assert java["sig.0.vrikey"] == expected_key
    # And that exact key is the (sole) /VRI entry.
    assert java["dss.vri.keys"] == expected_key


@requires_oracle
def test_ltv_append_preserves_original_signature(tmp_path: Path) -> None:
    """After the /DSS incremental append, PDFBox still verifies the original
    signature's detached CMS over its bracketed /ByteRange — the LTV revision
    was appended past the signed region, not written over it."""
    signed, cert, key = _build_signed_pdf(tmp_path)

    # Byte range PDFBox sees BEFORE the LTV add.
    before = _parse_probe_kv(run_probe_text("DssReadProbe", str(signed)))
    assert before["sig.count"] == "1"
    assert before["sig.0.digestIntact"] == "true"
    br_before = [int(x) for x in before["sig.0.byterange"].split(",")]

    out = tmp_path / "ltv_intact.pdf"
    _add_ltv_dss(signed, out, cert, key)

    after = _parse_probe_kv(run_probe_text("DssReadProbe", str(out)))
    # The signature still verifies — the signed bytes were not disturbed.
    assert after["sig.0.digestIntact"] == "true"
    # The original /ByteRange four-tuple is byte-for-byte identical: the LTV
    # revision lives strictly after the originally signed region.
    br_after = [int(x) for x in after["sig.0.byterange"].split(",")]
    assert br_after == br_before

    # The LTV file is strictly longer than the signed-only file (the /DSS
    # revision was appended).
    assert out.stat().st_size > signed.stat().st_size


@requires_oracle
def test_pypdfbox_dss_pools_without_vri_read_by_pdfbox(tmp_path: Path) -> None:
    """A /DSS carrying only document-wide pools (no /VRI) round-trips: PDFBox
    sees the pools and reports /VRI absent."""
    signed, cert, key = _build_signed_pdf(tmp_path)
    out = tmp_path / "ltv_no_vri.pdf"
    _add_ltv_dss(signed, out, cert, key, with_vri=False)

    java = _parse_probe_kv(run_probe_text("DssReadProbe", str(out)))
    assert java["dss.present"] == "true"
    assert java["dss.certs"] == "1"
    assert java["dss.crls"] == "1"
    assert java["dss.ocsps"] == "1"
    assert java["dss.vri.present"] == "false"
    assert java["dss.vri.keys"] == ""
    # The signature is still intact after the pools-only LTV append.
    assert java["sig.0.digestIntact"] == "true"


@requires_oracle
def test_pypdfbox_dss_multiple_certs_count_matches(tmp_path: Path) -> None:
    """A multi-cert chain in the /DSS pool surfaces the right /Certs count in
    PDFBox, and the per-VRI /Cert count agrees."""
    signed, leaf_cert, leaf_key = _build_signed_pdf(tmp_path)
    issuer_cert, _issuer_key = _make_self_signed_cert("pypdfbox-ltv-issuer")
    inter_cert, _inter_key = _make_self_signed_cert("pypdfbox-ltv-inter")

    bundle = collect_revocation_info(
        leaf_cert,
        intermediate_certs=[inter_cert],
        issuer_cert=issuer_cert,
    )
    assert len(bundle.certs) == 3

    out = tmp_path / "ltv_chain.pdf"
    with PDDocument.load(signed) as doc:
        sig = _signature_from_acroform(doc)
        contents = sig.get_contents()
        assert contents is not None
        expected_key = hashlib.sha1(contents).hexdigest().upper()  # noqa: S324
        dss = PDDocumentSecurityStore.ensure_on(doc)
        dss.bundle(certs=bundle.certs, signature=sig)
        doc.save_incremental(out)

    java = _parse_probe_kv(run_probe_text("DssReadProbe", str(out)))
    assert java["dss.certs"] == "3"
    # No CRLs/OCSPs supplied → those pool arrays are absent (-1 sentinel).
    assert java["dss.crls"] == "-1"
    assert java["dss.ocsps"] == "-1"
    assert java[f"vri.{expected_key}.cert"] == "3"
    assert java[f"vri.{expected_key}.crl"] == "-1"
    assert java["sig.0.digestIntact"] == "true"


@requires_oracle
def test_two_dss_certs_bundled_certs_persist(tmp_path: Path) -> None:
    """Bundling two certs into the document-wide /Certs pool surfaces a count
    of 2 in PDFBox, proving the COSArray of streams round-trips intact."""
    signed, cert, key = _build_signed_pdf(tmp_path)
    second_cert, _ = _make_self_signed_cert("pypdfbox-ltv-second")

    out = tmp_path / "ltv_two_certs.pdf"
    with PDDocument.load(signed) as doc:
        dss = PDDocumentSecurityStore.ensure_on(doc)
        dss.set_certs(
            [
                cert.public_bytes(Encoding.DER),
                second_cert.public_bytes(Encoding.DER),
            ]
        )
        doc.save_incremental(out)

    java = _parse_probe_kv(run_probe_text("DssReadProbe", str(out)))
    assert java["dss.present"] == "true"
    assert java["dss.certs"] == "2"
    assert java["sig.0.digestIntact"] == "true"
