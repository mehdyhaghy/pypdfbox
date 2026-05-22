"""Wave 1382 — close PDF/A LTV (Long-Term Validation) revocation-info
bundling gap (DSS / VRI).

Covers:

* :class:`PDDocumentSecurityStore` — typed wrappers for ``/DSS`` carry
  /Certs / /CRLs / /OCSPs / /VRI round-trip.
* :class:`PDValidationInformation` — per-signature ``/VRI`` entry
  carries /Cert / /CRL / /OCSP / /TS / /TU round-trip.
* :func:`collect_revocation_info` — assembles a
  :class:`RevocationInfoBundle` from a candidate cert chain.
* End-to-end LTV: synthetic signed PDF → reload → bundle /DSS +
  per-signature /VRI keyed on uppercase SHA-1 of /Contents → reload →
  /DSS shape round-trips, original signature /ByteRange survives, /VRI
  key matches the signature's /Contents digest.
"""

from __future__ import annotations

import datetime
import hashlib
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import ocsp
from cryptography.x509.oid import NameOID

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.examples.signature.cert import (
    RevocationInfoBundle,
    build_synthetic_crl,
    build_synthetic_ocsp_response,
    collect_revocation_info,
)
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature import (
    PDDocumentSecurityStore,
    PDSignature,
    PDValidationInformation,
    Pkcs7Signature,
)

# ---------- shared helpers ----------


def _make_self_signed_cert(
    cn: str = "pypdfbox wave 1382",
) -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-test"),
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


def _build_tiny_pdf(path: Path) -> Path:
    doc = PDDocument()
    try:
        doc.add_page(PDPage())
        doc.save(path)
    finally:
        doc.close()
    return path


def _build_signed_pdf(tmp_path: Path) -> tuple[Path, x509.Certificate, rsa.RSAPrivateKey]:
    cert, key = _make_self_signed_cert()
    src = _build_tiny_pdf(tmp_path / "in.pdf")
    signed = tmp_path / "signed.pdf"

    with PDDocument.load(src) as doc:
        sig = PDSignature()
        sig.set_name("LTV signer")
        sig.set_reason("wave 1382 LTV test")
        doc.add_signature(sig, Pkcs7Signature(cert, key))
        doc.save_incremental(signed)
    return signed, cert, key


# ---------- PDValidationInformation typed surface ----------


def test_pdvalidationinformation_round_trip() -> None:
    vri = PDValidationInformation()
    vri.set_certs([b"\x30\x82CERT1", b"\x30\x82CERT2"])
    vri.set_crls([b"\x30\x82CRL1"])
    vri.set_ocsps([b"\x30\x82OCSP1", b"\x30\x82OCSP2"])
    vri.set_timestamp(b"\x30\x82TSP")
    vri.set_validation_time("D:20260101000000Z")

    assert vri.get_certs() == [b"\x30\x82CERT1", b"\x30\x82CERT2"]
    assert vri.get_crls() == [b"\x30\x82CRL1"]
    assert vri.get_ocsps() == [b"\x30\x82OCSP1", b"\x30\x82OCSP2"]
    assert vri.get_timestamp() == b"\x30\x82TSP"
    assert vri.get_validation_time() == "D:20260101000000Z"


def test_pdvalidationinformation_clear() -> None:
    vri = PDValidationInformation()
    vri.set_certs([b"X"])
    vri.set_timestamp(b"Y")
    vri.set_validation_time("D:Z")

    vri.set_certs(None)
    vri.set_timestamp(None)
    vri.set_validation_time(None)

    assert vri.get_certs() == []
    assert vri.get_timestamp() is None
    assert vri.get_validation_time() is None


def test_pdvalidationinformation_accepts_existing_cos_stream() -> None:
    stream = COSStream()
    stream.set_data(b"DER-blob-bytes")

    vri = PDValidationInformation()
    vri.set_certs([stream])
    assert vri.get_certs() == [b"DER-blob-bytes"]


def test_pdvalidationinformation_set_certs_type_check() -> None:
    vri = PDValidationInformation()
    with pytest.raises(TypeError, match="bytes"):
        vri.set_certs([12345])  # type: ignore[list-item]


# ---------- PDDocumentSecurityStore typed surface ----------


def test_pddocumentsecuritystore_round_trip() -> None:
    dss = PDDocumentSecurityStore()
    dss.set_certs([b"DER-CERT-1", b"DER-CERT-2"])
    dss.set_crls([b"DER-CRL"])
    dss.set_ocsps([b"DER-OCSP-1"])

    assert dss.get_certs() == [b"DER-CERT-1", b"DER-CERT-2"]
    assert dss.get_crls() == [b"DER-CRL"]
    assert dss.get_ocsps() == [b"DER-OCSP-1"]


def test_pddocumentsecuritystore_set_type_stamped() -> None:
    dss = PDDocumentSecurityStore()
    type_entry = dss.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("Type")
    )
    assert isinstance(type_entry, COSName)
    assert type_entry.get_name() == "DSS"


def test_pddocumentsecuritystore_add_certs_appends() -> None:
    dss = PDDocumentSecurityStore()
    dss.add_certs([b"A"])
    dss.add_certs([b"B", b"C"])
    assert dss.get_certs() == [b"A", b"B", b"C"]


def test_pddocumentsecuritystore_add_crls_appends() -> None:
    dss = PDDocumentSecurityStore()
    dss.add_crls([b"A"])
    dss.add_crls([b"B"])
    assert dss.get_crls() == [b"A", b"B"]


def test_pddocumentsecuritystore_add_ocsps_appends() -> None:
    dss = PDDocumentSecurityStore()
    dss.add_ocsps([b"A"])
    dss.add_ocsps([b"B"])
    assert dss.get_ocsps() == [b"A", b"B"]


def test_pddocumentsecuritystore_clear_entries() -> None:
    dss = PDDocumentSecurityStore()
    dss.set_certs([b"X"])
    dss.set_crls([b"Y"])
    dss.set_ocsps([b"Z"])

    dss.set_certs(None)
    dss.set_crls(None)
    dss.set_ocsps(None)
    assert dss.get_certs() == []
    assert dss.get_crls() == []
    assert dss.get_ocsps() == []


def test_pddocumentsecuritystore_vri_default_absent() -> None:
    dss = PDDocumentSecurityStore()
    assert dss.get_vri_dictionary() is None


def test_pddocumentsecuritystore_ensure_vri_creates() -> None:
    dss = PDDocumentSecurityStore()
    vri = dss.ensure_vri_dictionary()
    assert isinstance(vri, COSDictionary)
    # Idempotent — second call returns the same instance.
    assert dss.ensure_vri_dictionary() is vri


def test_vri_key_for_signature_is_sha1_upper_hex() -> None:
    sig = PDSignature()
    sig.set_contents(b"the-contents-octet-string")
    key = PDDocumentSecurityStore._vri_key_for(sig)
    assert key == hashlib.sha1(b"the-contents-octet-string").hexdigest().upper()  # noqa: S324


def test_vri_key_for_signature_without_contents_raises() -> None:
    sig = PDSignature()
    with pytest.raises(ValueError, match="/Contents"):
        PDDocumentSecurityStore._vri_key_for(sig)


def test_vri_key_for_str_is_uppercased() -> None:
    assert PDDocumentSecurityStore._vri_key_for("deadbeef") == "DEADBEEF"


def test_vri_key_for_bytes_is_sha1_hex() -> None:
    blob = b"some-contents"
    expected = hashlib.sha1(blob).hexdigest().upper()  # noqa: S324
    assert PDDocumentSecurityStore._vri_key_for(blob) == expected


def test_vri_key_for_invalid_type_raises() -> None:
    with pytest.raises(TypeError, match="PDSignature"):
        PDDocumentSecurityStore._vri_key_for(123)  # type: ignore[arg-type]


def test_set_and_get_validation_information_round_trip() -> None:
    dss = PDDocumentSecurityStore()
    sig = PDSignature()
    sig.set_contents(b"SIG-BYTES")

    vri = PDValidationInformation()
    vri.set_certs([b"CERT-CHAIN-DER"])
    vri.set_crls([b"CRL-DER"])
    vri.set_ocsps([b"OCSP-DER"])
    dss.set_validation_information(sig, vri)

    looked_up = dss.get_validation_information(sig)
    assert looked_up is not None
    assert looked_up.get_certs() == [b"CERT-CHAIN-DER"]
    assert looked_up.get_crls() == [b"CRL-DER"]
    assert looked_up.get_ocsps() == [b"OCSP-DER"]


def test_get_validation_information_missing_returns_none() -> None:
    dss = PDDocumentSecurityStore()
    sig = PDSignature()
    sig.set_contents(b"NONE")
    assert dss.get_validation_information(sig) is None


def test_dss_bundle_writes_pools_and_vri() -> None:
    dss = PDDocumentSecurityStore()
    sig = PDSignature()
    sig.set_contents(b"SIG")

    info = dss.bundle(
        certs=[b"CERT-A", b"CERT-B"],
        crls=[b"CRL-A"],
        ocsps=[b"OCSP-A"],
        signature=sig,
    )

    # Pools populated.
    assert dss.get_certs() == [b"CERT-A", b"CERT-B"]
    assert dss.get_crls() == [b"CRL-A"]
    assert dss.get_ocsps() == [b"OCSP-A"]
    # Per-signature VRI populated.
    assert info is not None
    assert info.get_certs() == [b"CERT-A", b"CERT-B"]
    assert info.get_crls() == [b"CRL-A"]
    assert info.get_ocsps() == [b"OCSP-A"]


def test_dss_bundle_without_signature_returns_none() -> None:
    dss = PDDocumentSecurityStore()
    info = dss.bundle(certs=[b"X"])
    assert info is None
    assert dss.get_certs() == [b"X"]


# ---------- from_document / ensure_on ----------


def test_from_document_absent_returns_none(tmp_path: Path) -> None:
    src = _build_tiny_pdf(tmp_path / "plain.pdf")
    with PDDocument.load(src) as doc:
        assert PDDocumentSecurityStore.from_document(doc) is None


def test_ensure_on_creates_and_persists(tmp_path: Path) -> None:
    src = _build_tiny_pdf(tmp_path / "plain.pdf")
    with PDDocument.load(src) as doc:
        dss = PDDocumentSecurityStore.ensure_on(doc)
        assert isinstance(dss, PDDocumentSecurityStore)
        # The catalog now exposes /DSS via from_document.
        again = PDDocumentSecurityStore.from_document(doc)
        assert again is not None
        assert again.get_cos_object() is dss.get_cos_object()


# ---------- collect_revocation_info ----------


def test_collect_revocation_info_dedupes_chain() -> None:
    leaf, _ = _make_self_signed_cert("leaf")
    bundle = collect_revocation_info(leaf, intermediate_certs=[leaf, leaf])
    # Same cert listed three times — collapsed to one.
    assert len(bundle.certs) == 1
    assert bundle.certs[0] == leaf.public_bytes(Encoding.DER)


def test_collect_revocation_info_includes_issuer_and_intermediates() -> None:
    leaf, _ = _make_self_signed_cert("leaf")
    issuer, _ = _make_self_signed_cert("issuer")
    inter, _ = _make_self_signed_cert("intermediate")
    bundle = collect_revocation_info(
        leaf,
        intermediate_certs=[inter],
        issuer_cert=issuer,
    )
    # 3 distinct certs — order: leaf, issuer, intermediate.
    assert len(bundle.certs) == 3


def test_collect_revocation_info_packs_crls_and_ocsps() -> None:
    issuer, issuer_key = _make_self_signed_cert("ocsp-issuer")
    leaf, _leaf_key = _make_self_signed_cert("leaf")

    crl = build_synthetic_crl(
        issuer_cert=issuer,
        issuer_key=issuer_key,
    )
    ocsp_resp = build_synthetic_ocsp_response(
        subject_cert=leaf,
        issuer_cert=issuer,
        responder_cert=issuer,
        responder_key=issuer_key,
    )

    bundle = collect_revocation_info(
        leaf,
        intermediate_certs=[],
        issuer_cert=issuer,
        crls=[crl],
        ocsp_responses=[ocsp_resp],
    )
    assert bundle.crls == [crl.public_bytes(Encoding.DER)]
    assert bundle.ocsps == [ocsp_resp.public_bytes(Encoding.DER)]


def test_revocation_info_bundle_is_empty_predicate() -> None:
    assert RevocationInfoBundle(certs=[], crls=[], ocsps=[]).is_empty()
    assert not RevocationInfoBundle(certs=[b"X"], crls=[], ocsps=[]).is_empty()


def test_build_synthetic_ocsp_response_is_der_decodable() -> None:
    cert, key = _make_self_signed_cert("ocsp-test")
    resp = build_synthetic_ocsp_response(
        subject_cert=cert,
        issuer_cert=cert,
        responder_cert=cert,
        responder_key=key,
    )
    der = resp.public_bytes(Encoding.DER)
    parsed = ocsp.load_der_ocsp_response(der)
    assert parsed.response_status == ocsp.OCSPResponseStatus.SUCCESSFUL


def test_build_synthetic_crl_is_der_decodable() -> None:
    cert, key = _make_self_signed_cert("crl-test")
    crl = build_synthetic_crl(issuer_cert=cert, issuer_key=key)
    der = crl.public_bytes(Encoding.DER)
    parsed = x509.load_der_x509_crl(der)
    assert parsed.issuer == cert.subject


def test_build_synthetic_crl_records_revoked_serials() -> None:
    cert, key = _make_self_signed_cert("crl-rev")
    crl = build_synthetic_crl(
        issuer_cert=cert,
        issuer_key=key,
        revoked_serials=[42, 99],
    )
    serials = sorted(rev.serial_number for rev in crl)
    assert serials == [42, 99]


# ---------- end-to-end LTV embedding ----------


def test_dss_round_trip_in_signed_pdf(tmp_path: Path) -> None:
    """Sign a PDF, reload, bundle /DSS + per-sig /VRI, save_incremental,
    reload again, assert DSS structure survived and original signature's
    /ByteRange still spans the file.
    """
    signed, cert, key = _build_signed_pdf(tmp_path)
    out = tmp_path / "ltv.pdf"

    # Snapshot the byte length of the originally signed file so we can
    # verify the original /ByteRange is preserved through incremental
    # append of /DSS.
    signed_len = signed.stat().st_size

    # Build evidence offline.
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

    # Embed via DSS / VRI.
    with PDDocument.load(signed) as doc:
        acro = doc.get_document_catalog().get_acro_form()
        assert acro is not None
        sig_fields = acro.get_fields()
        assert len(sig_fields) == 1
        sig_dict = sig_fields[0].get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("V")
        )
        assert isinstance(sig_dict, COSDictionary)
        sig = PDSignature(sig_dict)

        dss = PDDocumentSecurityStore.ensure_on(doc)
        dss.bundle(
            certs=bundle.certs,
            crls=bundle.crls,
            ocsps=bundle.ocsps,
            signature=sig,
        )
        doc.save_incremental(out)

    # Reload the LTV-stamped file.
    with PDDocument.load(out) as reloaded:
        # /DSS lives on the catalog.
        dss = PDDocumentSecurityStore.from_document(reloaded)
        assert dss is not None
        assert dss.get_certs() == bundle.certs
        assert dss.get_crls() == bundle.crls
        assert dss.get_ocsps() == bundle.ocsps

        # /VRI keyed on the signature's /Contents SHA-1.
        acro = reloaded.get_document_catalog().get_acro_form()
        assert acro is not None
        fields = acro.get_fields()
        sig_dict = fields[0].get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("V")
        )
        assert isinstance(sig_dict, COSDictionary)
        reloaded_sig = PDSignature(sig_dict)

        info = dss.get_validation_information(reloaded_sig)
        assert info is not None
        assert info.get_certs() == bundle.certs
        assert info.get_crls() == bundle.crls
        assert info.get_ocsps() == bundle.ocsps

        # Per-spec key: uppercase SHA-1 hex of /Contents.
        vri_dict = dss.get_vri_dictionary()
        assert vri_dict is not None
        expected_key = hashlib.sha1(  # noqa: S324
            reloaded_sig.get_contents() or b""
        ).hexdigest().upper()
        assert vri_dict.get_dictionary_object(
            COSName.get_pdf_name(expected_key)
        ) is not None

        # Original signature ByteRange still bracket the file — the
        # /DSS incremental section is APPENDED past the signed region.
        br = reloaded_sig.get_byte_range()
        assert br is not None
        start1, len1, start2, len2 = br
        assert start1 == 0
        # The original signed bytes (signed_len) are still entirely
        # covered by the original /ByteRange (start1..start1+len1 +
        # start2..start2+len2 fit within signed_len).
        assert start2 + len2 == signed_len

        # The new (LTV) file is strictly longer than the original.
        assert out.stat().st_size > signed_len


def test_dss_embed_preserves_signature_contents_octet_string(tmp_path: Path) -> None:
    """The original signature's /Contents must not be mutated by the
    /DSS embedding pass — same bytes before and after."""
    signed, cert, key = _build_signed_pdf(tmp_path)
    out = tmp_path / "ltv2.pdf"

    # Snapshot original /Contents.
    with PDDocument.load(signed) as doc:
        sig_fields = doc.get_document_catalog().get_acro_form().get_fields()
        sig_dict = sig_fields[0].get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("V")
        )
        original_contents = PDSignature(sig_dict).get_contents()
    assert original_contents is not None

    # LTV pass.
    with PDDocument.load(signed) as doc:
        dss = PDDocumentSecurityStore.ensure_on(doc)
        dss.set_certs([cert.public_bytes(Encoding.DER)])
        doc.save_incremental(out)

    # Verify /Contents survived byte-for-byte.
    with PDDocument.load(out) as reloaded:
        sig_fields = reloaded.get_document_catalog().get_acro_form().get_fields()
        sig_dict = sig_fields[0].get_cos_object().get_dictionary_object(
            COSName.get_pdf_name("V")
        )
        assert PDSignature(sig_dict).get_contents() == original_contents
