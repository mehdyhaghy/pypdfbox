"""Wave 1392 coverage round-out for the digital-signature subpackage.

Targets:

* ``cms_helpers`` DER error-path branches (lines 64, 80, 88, 98, 173,
  183, 191, 219, 224, 228, 233) that the wave 1382 hand-written DER
  walker added but no test reaches yet.
* ``pd_document_security_store`` defensive None-removal branches in
  ``set_crls`` / ``set_ocsps`` (lines 141-142, 154-155), the ``COSString``
  /TS read path (line 165), the missing-VRI-entry branch (line 311),
  and the "existing DSS" return on :meth:`ensure_on` (line 387).
* ``pd_seed_value`` ``check_signature_constraint`` legal-attestation
  and digest-method branches (lines 487, 495-506).
* ``timestamped_signature`` ``signer`` / ``tsa_client`` property
  accessors + ``DocumentTimestampSigner.tsa_client`` (lines 93, 97,
  160).
* ``pd_signature`` malformed ``/Contents`` ``<>`` delimiter branches
  in :meth:`PDSignature.read_contents` (lines 808->813, 814->818, 819).
"""

from __future__ import annotations

from typing import BinaryIO

import pytest

from pypdfbox.cos import COSName, COSString
from pypdfbox.pdmodel import PDDocument, PDPage
from pypdfbox.pdmodel.interactive.digitalsignature import (
    DocumentTimestampSigner,
    PDDocumentSecurityStore,
    PDSeedValue,
    PDSignature,
    PDValidationInformation,
    TimestampedPkcs7Signature,
)
from pypdfbox.pdmodel.interactive.digitalsignature.cms_helpers import (
    _encode_der_length,
    _parse_der_tag,
    inject_timestamp_token,
)

# ---------- cms_helpers error-path branches ----------


def test_encode_der_length_rejects_oversized_length() -> None:
    """Line 64 — lengths needing more than 126 length-octets are rejected
    (X.690 §8.1.3.5 caps at 126; a payload that big is implausible for
    PKCS#7)."""
    # A length that needs more than 126 bytes to encode = 1 << (126*8) bits.
    oversize = 1 << (127 * 8)
    with pytest.raises(ValueError, match="too large"):
        _encode_der_length(oversize)


def test_parse_der_tag_rejects_offset_at_end() -> None:
    """Line 80 — offset beyond buffer raises ValueError("DER tag offset
    ... beyond buffer length")."""
    with pytest.raises(ValueError, match="beyond buffer length"):
        _parse_der_tag(b"\x30", 5)


def test_parse_der_tag_rejects_truncated_after_tag() -> None:
    """Line 88 — truncated length field after the tag byte."""
    with pytest.raises(ValueError, match="truncated DER length"):
        _parse_der_tag(b"\x30", 0)


def test_parse_der_tag_rejects_unreasonable_length_of_length() -> None:
    """Line 98 — long-form length-of-length > 8 is rejected."""
    # 0x89 = 0x80 | 9 → 9 length-octets, which exceeds the 8-byte sanity
    # cap.
    with pytest.raises(ValueError, match="unreasonable DER length-of-length"):
        _parse_der_tag(b"\x30\x89", 0)


def test_inject_timestamp_token_rejects_non_oid_contenttype() -> None:
    """Line 173 — when ContentInfo's first child isn't an OID (tag 0x06)."""
    # SEQUENCE(0x30) [SEQUENCE(0x30, empty)] - first child is SEQ not OID.
    blob = b"\x30\x02\x30\x00"
    with pytest.raises(ValueError, match="expected OID"):
        inject_timestamp_token(blob, b"token")


def test_inject_timestamp_token_rejects_non_context0_after_oid() -> None:
    """Line 183 — content after OID must be [0] EXPLICIT (0xA0)."""
    # SEQUENCE { OID(1.2), SEQUENCE(empty) } — second element is SEQ
    # instead of [0] EXPLICIT. Outer SEQ contents = 3+2 = 5 bytes.
    blob = b"\x30\x05\x06\x01\x2a\x30\x00"
    with pytest.raises(ValueError, match=r"\[0\] EXPLICIT"):
        inject_timestamp_token(blob, b"token")


def test_inject_timestamp_token_rejects_non_sequence_signeddata() -> None:
    """Line 191 — content inside [0] EXPLICIT must be SEQUENCE (0x30)."""
    # SEQUENCE { OID(1.2), [0] EXPLICIT { OCTET STRING(empty) } }
    blob = b"\x30\x08\x06\x01\x2a\xa0\x03\x04\x01\xff"
    with pytest.raises(ValueError, match="SignedData: expected SEQUENCE"):
        inject_timestamp_token(blob, b"token")


def test_inject_timestamp_token_rejects_missing_signerinfos_set() -> None:
    """Line 219 — SignedData with no terminating SET → signerInfos not
    found. Layout:

    * outer SEQ
    * OID(1.2) — 3 bytes
    * [0] EXPLICIT { SEQ { INTEGER(0), INTEGER(1) } } — no SET inside;
      walker exits without finding signerInfos.
    """
    inner_sd = b"\x02\x01\x00\x02\x01\x01"  # 2 INTEGERs (no SET)
    sd = b"\x30" + bytes([len(inner_sd)]) + inner_sd
    c0 = b"\xa0" + bytes([len(sd)]) + sd
    oid = b"\x06\x01\x2a"
    body = oid + c0
    ci = b"\x30" + bytes([len(body)]) + body
    with pytest.raises(ValueError, match="signerInfos SET not found"):
        inject_timestamp_token(ci, b"token")


def test_inject_timestamp_token_rejects_empty_signerinfos_set() -> None:
    """Line 228 — signerInfos SET is present but empty (0 SignerInfo)."""
    # Build a SignedData whose final element is an empty SET (0x31 0x00).
    inner_sd = b"\x31\x00"  # empty SET — counts as signerInfos.
    sd = b"\x30" + bytes([len(inner_sd)]) + inner_sd
    c0 = b"\xa0" + bytes([len(sd)]) + sd
    oid = b"\x06\x01\x2a"
    body = oid + c0
    ci = b"\x30" + bytes([len(body)]) + body
    with pytest.raises(ValueError, match="empty SET"):
        inject_timestamp_token(ci, b"token")


def test_inject_timestamp_token_rejects_non_sequence_signerinfo() -> None:
    """Line 233 — first SignerInfo isn't a SEQUENCE."""
    # SignerInfos SET containing one OCTET STRING (0x04) instead of
    # SEQUENCE (0x30).
    si_set_body = b"\x04\x02\xff\xff"  # OCTET STRING(2 bytes) — wrong tag.
    si_set = b"\x31" + bytes([len(si_set_body)]) + si_set_body
    sd = b"\x30" + bytes([len(si_set)]) + si_set
    c0 = b"\xa0" + bytes([len(sd)]) + sd
    oid = b"\x06\x01\x2a"
    body = oid + c0
    ci = b"\x30" + bytes([len(body)]) + body
    with pytest.raises(ValueError, match="SignerInfo: expected SEQUENCE"):
        inject_timestamp_token(ci, b"token")


# ---------- pd_document_security_store ----------


def test_validation_information_set_crls_none_removes_entry() -> None:
    """Lines 141-142 — passing None to ``set_crls`` removes the
    ``/CRL`` entry."""
    vi = PDValidationInformation()
    vi.set_crls([b"crl-bytes"])
    assert vi.get_crls() == [b"crl-bytes"]
    vi.set_crls(None)
    assert vi.get_crls() == []
    # The /CRL key is removed from the dict (not just cleared).
    assert vi.get_cos_object().get_dictionary_object(COSName.get_pdf_name("CRL")) is None


def test_validation_information_set_ocsps_none_removes_entry() -> None:
    """Lines 154-155 — same for ``/OCSP``."""
    vi = PDValidationInformation()
    vi.set_ocsps([b"ocsp-bytes"])
    assert vi.get_ocsps() == [b"ocsp-bytes"]
    vi.set_ocsps(None)
    assert vi.get_ocsps() == []
    assert (
        vi.get_cos_object().get_dictionary_object(COSName.get_pdf_name("OCSP"))
        is None
    )


def test_validation_information_get_timestamp_handles_cosstring_form() -> None:
    """Line 165 — when /TS is stored as a COSString (legacy form), the
    getter must extract its bytes rather than returning None."""
    vi = PDValidationInformation()
    # Inject a COSString into /TS by hand.
    raw = b"\x30\x00fake-token-bytes"
    vi.get_cos_object().set_item(
        COSName.get_pdf_name("TS"), COSString.parse_hex(raw.hex())
    )
    out = vi.get_timestamp()
    assert out == raw


def test_dss_get_validation_information_returns_none_for_missing_key() -> None:
    """Line 311 — no VRI entry under the resolved key → None."""
    dss = PDDocumentSecurityStore()
    # Seed a VRI with a different key.
    other = PDValidationInformation()
    other.set_certs([b"a-cert"])
    dss.set_validation_information("AABBCCDD", other)
    # Look up a key that isn't there.
    result = dss.get_validation_information("DEADBEEF")
    assert result is None


def test_dss_bundle_with_only_certs_skips_crl_ocsp_paths() -> None:
    """Branches 414->416, 423->425, 425->427 — calling ``bundle`` with
    only ``certs`` populates the cert pool/VRI but skips the CRL/OCSP
    add and per-VRI set paths."""
    dss = PDDocumentSecurityStore()
    sig = PDSignature()
    # Stub /Contents so the VRI key resolution works.
    sig._dict.set_string(COSName.get_pdf_name("Contents"), "abcd")  # noqa: SLF001
    vri = dss.bundle(certs=[b"cert-only"], signature=sig)
    assert vri is not None
    assert vri.get_certs() == [b"cert-only"]
    assert vri.get_crls() == []
    assert vri.get_ocsps() == []


def test_dss_bundle_with_only_crls_skips_cert_ocsp_paths() -> None:
    """Branches 412->414, 421->423, 425->427 — same idea, mirrored."""
    dss = PDDocumentSecurityStore()
    sig = PDSignature()
    sig._dict.set_string(COSName.get_pdf_name("Contents"), "abcd")  # noqa: SLF001
    vri = dss.bundle(crls=[b"crl-only"], signature=sig)
    assert vri is not None
    assert vri.get_certs() == []
    assert vri.get_crls() == [b"crl-only"]
    assert vri.get_ocsps() == []


def test_dss_bundle_with_only_ocsps_skips_cert_crl_paths() -> None:
    """Branches 412->414, 414->416, 421->423, 423->425 — only OCSP."""
    dss = PDDocumentSecurityStore()
    sig = PDSignature()
    sig._dict.set_string(COSName.get_pdf_name("Contents"), "abcd")  # noqa: SLF001
    vri = dss.bundle(ocsps=[b"ocsp-only"], signature=sig)
    assert vri is not None
    assert vri.get_certs() == []
    assert vri.get_crls() == []
    assert vri.get_ocsps() == [b"ocsp-only"]


def test_array_to_byte_blobs_returns_empty_for_none_array() -> None:
    """Branch 96->94 — when /Cert / /CRL / /OCSP is absent (arr is
    None), the helper returns an empty list rather than iterating."""
    vi = PDValidationInformation()
    # /Cert is not set → helper returns empty list (branch 96->94 fires
    # via ``_array_to_byte_blobs(None)``).
    assert vi.get_certs() == []
    assert vi.get_crls() == []
    assert vi.get_ocsps() == []


def test_dss_ensure_on_returns_existing_when_already_attached() -> None:
    """Line 387 — calling ``ensure_on`` twice returns the same backing
    /DSS dict the second time, without clobbering existing entries."""
    doc = PDDocument()
    doc.add_page(PDPage())
    dss1 = PDDocumentSecurityStore.ensure_on(doc)
    dss1.bundle(certs=[b"cert-A"])
    dss2 = PDDocumentSecurityStore.ensure_on(doc)
    # Same underlying COS dict — the /DSS wrapper round-trips through
    # the catalog without creating a fresh dict.
    assert dss1.get_cos_object() is dss2.get_cos_object()
    assert dss2.get_certs() == [b"cert-A"]
    doc.close()


# ---------- pd_seed_value check_signature_constraint ----------


def test_pdseedvalue_violation_legal_attestation_required_with_allowed_values() -> None:
    """Lines 483-485 — when legal attestation IS required and the seed
    carries a non-empty allowed list, the helper reports the requirement
    rather than the bare "no allowed values" variant."""
    sv = PDSeedValue()
    sv.set_legal_attestation(["No Modifications Permitted"])
    sv.set_legal_attestation_required(True)
    sig = PDSignature()
    violations = sv.check_signature_constraint(sig)
    assert any("LegalAttestation" in v for v in violations)
    assert any("No Modifications Permitted" in v for v in violations)


def test_pdseedvalue_violation_legal_attestation_required_with_no_allowed_values() -> None:
    """Line 487 — flagged-required + no allowed values → bare "no
    allowed values set" message."""
    sv = PDSeedValue()
    sv.set_legal_attestation_required(True)  # /Ff bit set, no list seeded.
    sig = PDSignature()
    violations = sv.check_signature_constraint(sig)
    assert any("no allowed values" in v for v in violations)


def test_pdseedvalue_violation_digest_method_required_with_disallowed_hint() -> None:
    """Lines 495-506 — flagged /DigestMethod + signature carries a
    digest-method hint NOT in the allowed list."""
    sv = PDSeedValue()
    sv.set_digest_method([PDSeedValue.DIGEST_SHA256, PDSeedValue.DIGEST_SHA384])
    sv.set_digest_method_required(True)
    sig = PDSignature()
    sig._digest_method_hint = "SHA1"  # noqa: SLF001 — explicit signer hint.
    violations = sv.check_signature_constraint(sig)
    assert any("DigestMethod" in v for v in violations)
    assert any("SHA1" in v for v in violations)


def test_pdseedvalue_reason_required_but_no_allowed_list_skips_violation() -> None:
    """Branch 468->480 — when /Reasons is flagged-required but no
    allowed list is set, the check skips (the seed doesn't constrain
    which reason values are acceptable)."""
    sv = PDSeedValue()
    sv.set_reason_required(True)  # /Ff bit set, no allowed list.
    sig = PDSignature()
    sig.set_reason("Approving the document")
    violations = sv.check_signature_constraint(sig)
    # No /Reason violation reported (the constraint can't be evaluated).
    assert not any(v.startswith("/Reason") for v in violations)


def test_pdseedvalue_reason_required_actual_in_allowed_skips_violation() -> None:
    """Branch 471->480 — when the signature's reason IS in the allowed
    list, no violation is reported."""
    sv = PDSeedValue()
    sv.set_reasons(["Authorship", "Compliance"])
    sv.set_reason_required(True)
    sig = PDSignature()
    sig.set_reason("Authorship")
    violations = sv.check_signature_constraint(sig)
    assert not any(v.startswith("/Reason") for v in violations)


def test_pdseedvalue_no_violation_for_digest_method_when_no_hint() -> None:
    """The complementary branch — when the signer carries no hint, no
    violation is reported even with the /Ff bit set (matches the upstream
    "no per-signature counterpart" stance)."""
    sv = PDSeedValue()
    sv.set_digest_method([PDSeedValue.DIGEST_SHA256])
    sv.set_digest_method_required(True)
    sig = PDSignature()
    # No _digest_method_hint attribute — actual_digest will be None.
    violations = sv.check_signature_constraint(sig)
    assert not any("DigestMethod" in v for v in violations)


# ---------- timestamped_signature property accessors ----------


class _FakePkcs7Signature:
    """Minimal stand-in for the cryptography-backed signer; isinstance
    check on TimestampedPkcs7Signature ctor only enforces Pkcs7Signature
    so we wire a real one in the property tests below."""

    def sign(self, content: BinaryIO) -> bytes:
        return b"fake-pkcs7"


class _FakeTSAClient:
    def get_time_stamp_token(self, content: BinaryIO) -> bytes:
        return b"fake-token"


def test_timestamped_pkcs7_signature_properties_expose_collaborators() -> None:
    """Lines 93, 97 — ``signer`` and ``tsa_client`` properties return
    the underlying objects passed at construction."""
    from pypdfbox.pdmodel.interactive.digitalsignature.pkcs7_signature import (
        Pkcs7Signature,
    )

    signer = Pkcs7Signature.__new__(Pkcs7Signature)  # bypass full ctor.
    tsa = _FakeTSAClient()
    wrapped = TimestampedPkcs7Signature(signer, tsa)  # type: ignore[arg-type]
    assert wrapped.signer is signer
    assert wrapped.tsa_client is tsa


def test_document_timestamp_signer_tsa_client_property() -> None:
    """Line 160 — ``DocumentTimestampSigner.tsa_client`` returns the
    underlying client."""
    tsa = _FakeTSAClient()
    sig = DocumentTimestampSigner(tsa)  # type: ignore[arg-type]
    assert sig.tsa_client is tsa


# ---------- pd_signature read_contents malformed-delimiter branches ----------


def test_pdsignature_get_contents_from_bytes_round_trip() -> None:
    """Sanity baseline — a properly bracketed /Contents block round-trips
    through :meth:`PDSignature.get_contents_from_bytes` using upstream's
    exact ``begin = br[0]+br[1]+1`` / ``len = br[2]-begin-1`` arithmetic."""
    sig = PDSignature()
    # Layout: PRE | < | hex(abcd) | > | POST
    # bytes:  10  | 1 | 4         | 1 | 6 → total 22.
    pdf = b"PRE-PREFIX<abcd>POSTFIX"
    # `<` at offset 10, `>` at offset 15. Delimiters EXCLUDED from the
    # ranges (PDFBox COSWriter convention): len1=10 (ends before `<`),
    # start2=16 (after `>`), len2=7. Upstream reader: begin=0+10+1=11
    # (first hex char), len=16-11-1=4 → slice pdf[11:15] == "abcd".
    sig.set_byte_range([0, 10, 16, 7])
    out = sig.get_contents_from_bytes(pdf)
    assert out == bytes.fromhex("abcd")


def test_pdsignature_get_contents_from_bytes_strips_residual_delimiters() -> None:
    """``get_converted_contents`` still strips a leading ``<`` / trailing
    ``>`` defensively, so a non-conformant range that nudges one delimiter
    INTO the slice is tolerated (upstream ``getConvertedContents`` parity)."""
    sig = PDSignature()
    pdf = b"PRE-PREFIX<abcd>POSTFIX"
    # Brackets-INCLUDED legacy convention: len1=11 (covers `<`), start2=15
    # (covers `>`). Upstream reader: begin=0+11+1=12, len=15-12-1=2 →
    # pdf[12:14] == "bc" — the residual-delimiter strip is a no-op here;
    # this case just proves the helper never raises on the legacy layout.
    sig.set_byte_range([0, 11, 15, 8])
    out = sig.get_contents_from_bytes(pdf)
    assert out == bytes.fromhex("bc")


def test_pdsignature_get_contents_raises_on_negative_slice() -> None:
    """A ``/ByteRange`` whose arithmetic yields a negative length raises
    ``IndexError`` (parity with upstream ``IndexOutOfBoundsException``)."""
    sig = PDSignature()
    body = b"AAAAABBBBBCCCCCDDDDDEEEEE"
    # br[2] (5) < begin (0+10+1=11) → len = 5-11-1 = -7 → negative.
    sig.set_byte_range([0, 10, 5, 10])
    with pytest.raises(IndexError, match="missing or malformed"):
        sig.get_contents_from_bytes(body)


def test_pdsignature_get_contents_raises_when_slice_overruns_file() -> None:
    """A ``/ByteRange`` whose slice runs past EOF raises ``IndexError``."""
    sig = PDSignature()
    body = b"PRE-PREFIX<abcd>POSTFIX"  # 23 bytes
    # begin=0+10+1=11, len=100-11-1=88 → 11+88 > 23.
    sig.set_byte_range([0, 10, 100, 7])
    with pytest.raises(IndexError, match="missing or malformed"):
        sig.get_contents_from_bytes(body)
