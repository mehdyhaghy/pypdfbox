"""Wave 1382 — CMS ``id-aa-timeStampToken`` unsigned-attribute embedder.

Covers
:func:`pypdfbox.pdmodel.interactive.digitalsignature.cms_helpers.inject_timestamp_token`
and the wave-1382 default ``embed_timestamp=True`` wiring on
:class:`TimestampedPkcs7Signature`. The injector is a minimal DER walker
that locates ``ContentInfo → SignedData → SignerInfos → SignerInfo`` and
splices an ``[1] IMPLICIT SET OF Attribute`` carrying the RFC 3161
timestamp token. This closes the wave 1380 deferral.

Test strategy:

* Direct DER tag/length helper round-trips for the parser primitives.
* End-to-end: feed a real ``cryptography``-produced PKCS#7 detached
  SignedData into :func:`inject_timestamp_token` with a DER-shaped
  synthetic token, then re-parse the modified blob with
  ``cryptography``'s ``load_der_pkcs7_certificates`` (structural
  invariant) and walk the SignerInfo manually to confirm the
  ``id-aa-timeStampToken`` OID is in fact present at the right depth.
* :class:`TimestampedPkcs7Signature` with ``embed_timestamp=True`` and
  a fake TSA returning a DER-shaped token: the produced PKCS#7 round
  trips through ``cryptography`` and carries the OID.
"""

from __future__ import annotations

import datetime
import hashlib
import io

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID

from pypdfbox.examples.signature.tsa_client import TSAClient
from pypdfbox.pdmodel.interactive.digitalsignature import (
    Pkcs7Signature,
    TimestampedPkcs7Signature,
)
from pypdfbox.pdmodel.interactive.digitalsignature.cms_helpers import (
    _build_time_stamp_attribute,
    _encode_der_length,
    _parse_der_tag,
    _wrap_tlv,
    inject_timestamp_token,
)

# Reusable DER OID for the embedded attribute (id-aa-timeStampToken).
_ID_AA_TS_OID_DER = bytes.fromhex("060B2A864886F70D010910020E")


# ---------- DER primitives ----------


@pytest.mark.parametrize(
    ("length", "expected"),
    [
        (0, b"\x00"),
        (1, b"\x01"),
        (127, b"\x7f"),
        (128, b"\x81\x80"),
        (255, b"\x81\xff"),
        (256, b"\x82\x01\x00"),
        (65535, b"\x82\xff\xff"),
        (65536, b"\x83\x01\x00\x00"),
    ],
    ids=[
        "zero",
        "one",
        "max_short",
        "min_long_1",
        "max_8bit",
        "min_2byte",
        "max_2byte",
        "min_3byte",
    ],
)
def test_encode_der_length(length: int, expected: bytes) -> None:
    assert _encode_der_length(length) == expected


def test_encode_der_length_negative_rejected() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        _encode_der_length(-1)


@pytest.mark.parametrize(
    ("tlv", "expected_tag", "expected_length", "expected_content_offset"),
    [
        (b"\x04\x05hello", 0x04, 5, 2),
        (b"\x30\x00", 0x30, 0, 2),
        (b"\x30\x81\x80" + b"\x00" * 0x80, 0x30, 0x80, 3),
        (b"\x30\x82\x01\x00" + b"\x00" * 0x100, 0x30, 0x100, 4),
        (b"\xa1\x03\x31\x01X", 0xA1, 3, 2),
    ],
    ids=["short", "empty", "long_1byte", "long_2byte", "context_a1"],
)
def test_parse_der_tag(
    tlv: bytes, expected_tag: int, expected_length: int, expected_content_offset: int
) -> None:
    tag, length, content = _parse_der_tag(tlv, 0)
    assert tag == expected_tag
    assert length == expected_length
    assert content == expected_content_offset


def test_parse_der_tag_indefinite_rejected() -> None:
    # 0x80 = indefinite form (BER only, illegal in DER).
    with pytest.raises(ValueError, match="indefinite-length"):
        _parse_der_tag(b"\x30\x80\x00\x00", 0)


def test_parse_der_tag_truncated_rejected() -> None:
    # Long-form length advertises 3 bytes but only 1 is present.
    with pytest.raises(ValueError, match="truncated"):
        _parse_der_tag(b"\x30\x83\x01", 0)


def test_parse_der_tag_content_runs_past_buffer_rejected() -> None:
    # SEQUENCE claims length 99 but only 2 bytes follow.
    with pytest.raises(ValueError, match="past buffer"):
        _parse_der_tag(b"\x30\x63ab", 0)


def test_parse_der_tag_high_tag_rejected() -> None:
    # 0x1F = high-tag-number form (multi-byte tag) — we don't need it.
    with pytest.raises(ValueError, match="high-tag-number"):
        _parse_der_tag(b"\x1f\x01\x02\x00", 0)


def test_der_round_trip() -> None:
    """Re-encoding a parsed TLV reproduces the original bytes."""
    payload = b"hello world" * 30
    blob = _wrap_tlv(0x30, payload)
    tag, length, content = _parse_der_tag(blob, 0)
    assert tag == 0x30
    assert length == len(payload)
    assert blob[content : content + length] == payload
    # Re-wrap → identical bytes.
    assert _wrap_tlv(tag, blob[content : content + length]) == blob


# ---------- _build_time_stamp_attribute ----------


def test_build_time_stamp_attribute_structure() -> None:
    fake_token = bytes([0x30, 0x04, 0xDE, 0xAD, 0xBE, 0xEF])  # DER SEQUENCE
    attr = _build_time_stamp_attribute(fake_token)
    # Outer SEQUENCE
    tag, length, content = _parse_der_tag(attr, 0)
    assert tag == 0x30
    body = attr[content : content + length]
    # First child: OID
    assert body.startswith(_ID_AA_TS_OID_DER)
    rest = body[len(_ID_AA_TS_OID_DER) :]
    set_tag, set_len, set_content = _parse_der_tag(rest, 0)
    assert set_tag == 0x31  # SET
    assert rest[set_content : set_content + set_len] == fake_token


# ---------- inject_timestamp_token: with a real cryptography PKCS#7 ----------


def _self_signed_cert() -> tuple[x509.Certificate, rsa.RSAPrivateKey]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subj = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "pypdfbox-wave-1382"),
            x509.NameAttribute(NameOID.COMMON_NAME, "wave 1382 signer"),
        ]
    )
    now = datetime.datetime.now(tz=datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subj)
        .issuer_name(subj)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return cert, key


def _make_pkcs7_blob() -> bytes:
    cert, key = _self_signed_cert()
    return pkcs7.PKCS7SignatureBuilder().set_data(b"document bytes to sign").add_signer(
        cert, key, hashes.SHA256()
    ).sign(
        serialization.Encoding.DER,
        [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary],
    )


def _make_fake_token() -> bytes:
    """Return a DER SEQUENCE whose content is meaningless but
    structurally valid (so OpenSSL won't reject the SignerInfo).
    Real RFC 3161 TimeStampToken bytes are also DER SEQUENCEs, so
    this is a faithful structural stand-in."""
    inner = b"\x04\x10" + bytes(range(16))  # OCTET STRING of 16 bytes
    return b"\x30" + _encode_der_length(len(inner)) + inner


def _find_oid_in(buf: bytes, oid_der: bytes) -> bool:
    """Return True if ``oid_der`` appears anywhere in ``buf``. Cheap
    sanity probe — for fine-grained location we walk the SignerInfo
    directly in the test below."""
    return oid_der in buf


def test_inject_timestamp_token_into_real_pkcs7_parses_with_cryptography() -> None:
    blob = _make_pkcs7_blob()
    out = inject_timestamp_token(blob, _make_fake_token())

    # Outer length must grow (we added attribute bytes).
    assert len(out) > len(blob)

    # OID must be present.
    assert _find_oid_in(out, _ID_AA_TS_OID_DER)

    # ``cryptography`` must still parse the result.
    certs = pkcs7.load_der_pkcs7_certificates(out)
    assert len(certs) >= 1


def test_inject_timestamp_token_walks_to_correct_signer_info_position() -> None:
    """Verify the injected attribute lives inside the first
    SignerInfo's ``unsignedAttrs`` ``[1] IMPLICIT SET``, not elsewhere
    in the blob (where the OID could coincidentally appear and pass a
    naive substring check)."""
    fake_token = _make_fake_token()
    blob = _make_pkcs7_blob()
    out = inject_timestamp_token(blob, fake_token)

    # Walk: ContentInfo SEQUENCE → OID → [0] EXPLICIT → SignedData SEQUENCE
    ci_tag, ci_len, ci_content = _parse_der_tag(out, 0)
    assert ci_tag == 0x30
    ct_tag, ct_len, ct_content = _parse_der_tag(out, ci_content)
    assert ct_tag == 0x06
    c0_tag, c0_len, c0_content = _parse_der_tag(out, ct_content + ct_len)
    assert c0_tag == 0xA0
    sd_tag, sd_len, sd_content = _parse_der_tag(out, c0_content)
    assert sd_tag == 0x30

    # Final element of SignedData is signerInfos SET (0x31).
    pos = sd_content
    sd_end = sd_content + sd_len
    signer_infos_off = None
    while pos < sd_end:
        tag, length, content = _parse_der_tag(out, pos)
        if content + length == sd_end and tag == 0x31:
            signer_infos_off = pos
            break
        pos = content + length
    assert signer_infos_off is not None

    set_tag, set_len, set_content = _parse_der_tag(out, signer_infos_off)
    # First SignerInfo SEQUENCE.
    si_tag, si_len, si_content = _parse_der_tag(out, set_content)
    assert si_tag == 0x30

    # Walk SignerInfo children — the LAST element should be the
    # ``[1] IMPLICIT SET`` we inserted (0xA1).
    pos = si_content
    si_end = si_content + si_len
    found_unsigned_attrs = False
    while pos < si_end:
        tag, length, content = _parse_der_tag(out, pos)
        if tag == 0xA1:
            found_unsigned_attrs = True
            # The OID we expect lives inside this SET → first Attribute
            # SEQUENCE → first child OID.
            attr_tag, attr_len, attr_content = _parse_der_tag(out, content)
            assert attr_tag == 0x30  # Attribute SEQUENCE
            oid_tag, oid_len, oid_content = _parse_der_tag(out, attr_content)
            assert oid_tag == 0x06  # OID
            actual_oid = out[oid_content - 2 : oid_content + oid_len]
            assert actual_oid == _ID_AA_TS_OID_DER
            break
        pos = content + length
    assert found_unsigned_attrs, "wave 1382: unsignedAttrs [1] IMPLICIT SET missing"


def test_inject_timestamp_token_extends_existing_unsigned_attrs() -> None:
    """When a SignerInfo already carries an unsignedAttrs ``[1]`` SET,
    the new Attribute is APPENDED to that SET (the SET is not replaced
    or duplicated). We verify by walking the resulting DER and
    confirming exactly one ``[1] IMPLICIT SET`` exists on the
    SignerInfo and it contains two Attribute SEQUENCEs.

    Note: PyCA's strict DER re-parse would warn on the resulting blob
    because RFC 5652 §11.6 mandates canonical SET ordering for SET OF
    Attribute and two same-OID attributes break that canonical order.
    Production callers never inject twice; this test only verifies the
    extend-vs-replace policy of the injector itself.
    """
    blob = _make_pkcs7_blob()
    out1 = inject_timestamp_token(blob, _make_fake_token())
    second_token = b"\x30\x06\x04\x04abcd"
    out2 = inject_timestamp_token(out1, second_token)

    # Walk the resulting DER and count the ``[1] IMPLICIT SET`` headers
    # found inside the first SignerInfo.
    ci_tag, ci_len, ci_content = _parse_der_tag(out2, 0)
    ct_tag, ct_len, ct_content = _parse_der_tag(out2, ci_content)
    c0_tag, c0_len, c0_content = _parse_der_tag(out2, ct_content + ct_len)
    sd_tag, sd_len, sd_content = _parse_der_tag(out2, c0_content)

    pos = sd_content
    sd_end = sd_content + sd_len
    signer_infos_off = None
    while pos < sd_end:
        tag, length, content = _parse_der_tag(out2, pos)
        if content + length == sd_end and tag == 0x31:
            signer_infos_off = pos
            break
        pos = content + length
    assert signer_infos_off is not None

    _, _, set_content = _parse_der_tag(out2, signer_infos_off)
    si_tag, si_len, si_content = _parse_der_tag(out2, set_content)
    assert si_tag == 0x30

    unsigned_attrs_count = 0
    attribute_count = 0
    pos = si_content
    si_end = si_content + si_len
    while pos < si_end:
        tag, length, content = _parse_der_tag(out2, pos)
        if tag == 0xA1:
            unsigned_attrs_count += 1
            # Walk inner Attribute SEQUENCEs.
            inner_pos = content
            inner_end = content + length
            while inner_pos < inner_end:
                a_tag, a_len, a_content = _parse_der_tag(out2, inner_pos)
                assert a_tag == 0x30
                attribute_count += 1
                inner_pos = a_content + a_len
        pos = content + length

    assert unsigned_attrs_count == 1, "extend must not introduce a second [1] SET"
    assert attribute_count == 2, "both Attribute SEQUENCEs must be present"


def test_inject_timestamp_token_rejects_non_bytes_blob() -> None:
    with pytest.raises(TypeError, match="bytes"):
        inject_timestamp_token("not bytes", b"\x30\x00")  # type: ignore[arg-type]


def test_inject_timestamp_token_rejects_non_bytes_token() -> None:
    with pytest.raises(TypeError, match="bytes"):
        inject_timestamp_token(b"\x30\x00", "not bytes")  # type: ignore[arg-type]


def test_inject_timestamp_token_rejects_empty_token() -> None:
    with pytest.raises(ValueError, match="empty"):
        inject_timestamp_token(_make_pkcs7_blob(), b"")


def test_inject_timestamp_token_rejects_non_contentinfo_sequence() -> None:
    # An OCTET STRING is not a ContentInfo.
    with pytest.raises(ValueError, match="ContentInfo: expected SEQUENCE"):
        inject_timestamp_token(b"\x04\x02ok", _make_fake_token())


def test_inject_timestamp_token_rejects_trailing_garbage() -> None:
    blob = _make_pkcs7_blob()
    with pytest.raises(ValueError, match="trailing bytes"):
        inject_timestamp_token(blob + b"\x00\x00", _make_fake_token())


# ---------- TimestampedPkcs7Signature ``embed_timestamp=True`` ----------


def _fake_tsa_returning(token: bytes):
    def _transport(request: bytes, url: str, headers: dict[str, str]) -> bytes:
        assert request
        return token
    return _transport


def test_timestamped_pkcs7_signature_default_embeds_token() -> None:
    cert, key = _self_signed_cert()
    fake_token = _make_fake_token()
    tsa = TSAClient(
        url="http://tsa.example/",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=_fake_tsa_returning(fake_token),
    )

    signer = Pkcs7Signature(cert, key)
    ts_signer = TimestampedPkcs7Signature(signer, tsa)  # embed default True
    assert ts_signer.embed_timestamp is True

    pkcs7_bytes = ts_signer.sign(io.BytesIO(b"payload to sign"))

    # The OID must appear in the produced blob (it was embedded).
    assert _ID_AA_TS_OID_DER in pkcs7_bytes
    # cryptography re-parses the modified blob.
    certs = pkcs7.load_der_pkcs7_certificates(pkcs7_bytes)
    assert any(c.subject == cert.subject for c in certs)
    # The token attribute is preserved on the signer instance too.
    assert ts_signer.last_time_stamp_token == fake_token


def test_timestamped_pkcs7_signature_embed_false_leaves_blob_untouched() -> None:
    cert, key = _self_signed_cert()
    fake_token = _make_fake_token()
    tsa = TSAClient(
        url="http://tsa.example/",
        username=None,
        password=None,
        digest=hashlib.sha256(),
        transport=_fake_tsa_returning(fake_token),
    )

    inner = Pkcs7Signature(cert, key)
    ts_signer = TimestampedPkcs7Signature(inner, tsa, embed_timestamp=False)
    pkcs7_bytes = ts_signer.sign(io.BytesIO(b"payload to sign"))

    # The OID must NOT appear — the blob is the raw PKCS#7 without
    # the unsigned-attribute splice.
    assert _ID_AA_TS_OID_DER not in pkcs7_bytes
    # Token is still exposed on the attribute.
    assert ts_signer.last_time_stamp_token == fake_token


def test_timestamped_pkcs7_signature_embed_property_round_trip() -> None:
    cert, key = _self_signed_cert()
    tsa = TSAClient(
        url="http://tsa.example/",
        username=None,
        password=None,
        digest=hashlib.sha256(),
    )
    ts_signer = TimestampedPkcs7Signature(Pkcs7Signature(cert, key), tsa)
    assert ts_signer.embed_timestamp is True
    ts_signer2 = TimestampedPkcs7Signature(
        Pkcs7Signature(cert, key), tsa, embed_timestamp=False
    )
    assert ts_signer2.embed_timestamp is False
