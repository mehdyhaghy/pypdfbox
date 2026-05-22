"""CMS / PKCS#7 ASN.1 helpers (wave 1382).

PyCA ``cryptography``'s ``PKCS7SignatureBuilder`` produces a complete
DER-encoded ``ContentInfo`` (RFC 5652 §3) wrapping ``SignedData``
(§5.1) but does not expose any way to insert unsigned attributes
(§5.3 ``SignerInfo.unsignedAttrs``). When pypdfbox builds a
TSA-timestamped signature, the RFC 3161 timestamp token must travel
inside the SignerInfo's ``unsignedAttrs`` SET as the
``id-aa-timeStampToken`` attribute (OID ``1.2.840.113549.1.9.16.2.14``,
RFC 3161 §3.3.2).

Rather than adding an ASN.1 dependency (`asn1crypto`, `pyasn1`) we do a
**minimal DER walk** of the produced PKCS#7 blob, locate the first
SignerInfo, splice in (or extend) the ``[1] IMPLICIT SET OF
Attribute`` unsigned-attrs container, and re-encode the affected
length headers up the containment chain
``ContentInfo → SignedData → SignerInfos → SignerInfo``.

DER essentials we need (X.690 §8):

* Identifier octet (1 byte for the tags we encounter — no high-tag
  numbers): bit 8/7 = class, bit 6 = constructed flag, bits 5-1 =
  number.
* Length octets — short form for ``< 128``; long form ``0x80 | n``
  followed by ``n`` big-endian bytes.

Tags we manipulate:

* ``0x30`` — SEQUENCE (constructed, universal 16)
* ``0x31`` — SET (constructed, universal 17)
* ``0xA0`` — ``[0] IMPLICIT`` constructed (used by SignedData for the
  ``content`` field in ContentInfo)
* ``0xA1`` — ``[1] IMPLICIT`` constructed (used by SignerInfo for the
  ``unsignedAttrs`` field)

This module intentionally exposes only the smallest possible surface
to keep the DER plumbing auditable.
"""

from __future__ import annotations

# OID 1.2.840.113549.1.9.16.2.14  (id-aa-timeStampToken, RFC 3161 §3.3.2).
# Encoded as a DER OID: 06 0B 2A 86 48 86 F7 0D 01 09 10 02 0E.
_ID_AA_TIME_STAMP_TOKEN_OID_DER: bytes = bytes(
    [0x06, 0x0B, 0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x09, 0x10, 0x02, 0x0E]
)


def _encode_der_length(length: int) -> bytes:
    """Encode ``length`` as DER length octets (X.690 §8.1.3).

    Short form when ``length < 128`` (single byte); otherwise long form
    ``0x80 | n`` followed by ``n`` big-endian bytes carrying the length.
    """
    if length < 0:
        raise ValueError(f"DER length must be non-negative, got {length}")
    if length < 0x80:
        return bytes([length])
    # Long form — emit the minimum number of bytes needed.
    body = length.to_bytes((length.bit_length() + 7) // 8, "big")
    if len(body) > 0x7E:
        # X.690 §8.1.3.5 allows up to 126 length-octets; a single PKCS#7
        # blob bigger than that is implausible in practice.
        raise ValueError(f"DER length too large to encode: {length}")
    return bytes([0x80 | len(body)]) + body


def _parse_der_tag(buf: bytes, offset: int) -> tuple[int, int, int]:
    """Parse one DER TLV header starting at ``offset`` in ``buf``.

    Returns ``(tag, length, content_offset)`` where ``content_offset``
    is the position of the first content byte (i.e. ``offset`` plus
    the bytes consumed by the tag and length fields).

    Only handles the tag forms we need: low-tag-number identifiers
    (single tag byte). High-tag-number form (``tag & 0x1F == 0x1F``)
    is rejected — PKCS#7 doesn't use it.
    """
    if offset >= len(buf):
        raise ValueError(f"DER tag offset {offset} beyond buffer length {len(buf)}")
    tag = buf[offset]
    if (tag & 0x1F) == 0x1F:
        raise ValueError(
            f"high-tag-number DER form not supported (tag={tag:#04x} at {offset})"
        )
    pos = offset + 1
    if pos >= len(buf):
        raise ValueError(f"truncated DER length at offset {pos}")
    first = buf[pos]
    pos += 1
    if first < 0x80:
        length = first
    elif first == 0x80:
        raise ValueError(f"indefinite-length DER form not allowed in DER at {offset}")
    else:
        n = first & 0x7F
        if n > 8:
            raise ValueError(f"unreasonable DER length-of-length {n} at {offset}")
        if pos + n > len(buf):
            raise ValueError(f"truncated DER long-form length at {pos}")
        length = int.from_bytes(buf[pos : pos + n], "big")
        pos += n
    if pos + length > len(buf):
        raise ValueError(
            f"DER content runs past buffer (offset={offset}, "
            f"length={length}, buf_len={len(buf)})"
        )
    return tag, length, pos


def _wrap_tlv(tag: int, content: bytes) -> bytes:
    """Wrap ``content`` in a TLV header with ``tag``."""
    return bytes([tag]) + _encode_der_length(len(content)) + content


def _build_time_stamp_attribute(tstoken: bytes) -> bytes:
    """Build the ``Attribute`` SEQUENCE for ``id-aa-timeStampToken``.

    ::

        Attribute ::= SEQUENCE {
            attrType  OBJECT IDENTIFIER,
            attrValues SET OF AttributeValue
        }

    For ``id-aa-timeStampToken`` the single AttributeValue is the
    RFC 3161 ``TimeStampToken`` (already a fully-formed ContentInfo
    wrapping SignedData wrapping TSTInfo — see RFC 3161 §2.4.2).
    """
    attr_values_set = _wrap_tlv(0x31, tstoken)  # SET OF AttributeValue
    return _wrap_tlv(0x30, _ID_AA_TIME_STAMP_TOKEN_OID_DER + attr_values_set)


def inject_timestamp_token(pkcs7_blob: bytes, tstoken: bytes) -> bytes:
    """Splice an ``id-aa-timeStampToken`` unsigned attribute carrying
    ``tstoken`` into the first SignerInfo of the ContentInfo
    ``pkcs7_blob``.

    The injected attribute is added to the existing
    ``unsignedAttrs`` ``[1] IMPLICIT SET`` if one is already present
    on the SignerInfo (typical PyCA output has no unsigned attrs at
    all). Length octets are re-encoded all the way up the containment
    chain so the returned blob remains a valid DER ContentInfo.

    Returns the rewritten DER bytes. ``pkcs7_blob`` is not mutated.

    Raises ``ValueError`` if ``pkcs7_blob`` is not a recognisable PKCS#7
    detached SignedData ContentInfo.
    """
    if not isinstance(pkcs7_blob, (bytes, bytearray)):
        raise TypeError(
            f"pkcs7_blob must be bytes, got {type(pkcs7_blob).__name__}"
        )
    if not isinstance(tstoken, (bytes, bytearray)):
        raise TypeError(f"tstoken must be bytes, got {type(tstoken).__name__}")
    if len(tstoken) == 0:
        raise ValueError("tstoken must not be empty")
    buf = bytes(pkcs7_blob)

    # ---- 1. ContentInfo SEQUENCE
    ci_tag, ci_len, ci_content = _parse_der_tag(buf, 0)
    if ci_tag != 0x30:
        raise ValueError(
            f"PKCS#7 ContentInfo: expected SEQUENCE (0x30), got {ci_tag:#04x}"
        )
    if ci_content + ci_len != len(buf):
        raise ValueError("PKCS#7 ContentInfo: trailing bytes after SEQUENCE content")

    # ContentInfo ::= SEQUENCE { contentType OID, content [0] EXPLICIT ANY }
    # contentType OID
    ct_tag, ct_len, ct_content = _parse_der_tag(buf, ci_content)
    if ct_tag != 0x06:
        raise ValueError(
            f"PKCS#7 ContentInfo: expected OID (0x06), got {ct_tag:#04x}"
        )
    # We don't strictly need to check the OID is signed-data
    # (1.2.840.113549.1.7.2) — but cheap and clearer to fail loudly.
    after_oid = ct_content + ct_len

    # [0] EXPLICIT — constructed context-specific 0 = 0xA0
    c0_tag, c0_len, c0_content = _parse_der_tag(buf, after_oid)
    if c0_tag != 0xA0:
        raise ValueError(
            f"PKCS#7 ContentInfo content tag: expected [0] EXPLICIT (0xA0), "
            f"got {c0_tag:#04x}"
        )

    # ---- 2. SignedData SEQUENCE inside [0] EXPLICIT
    sd_tag, sd_len, sd_content = _parse_der_tag(buf, c0_content)
    if sd_tag != 0x30:
        raise ValueError(
            f"PKCS#7 SignedData: expected SEQUENCE (0x30), got {sd_tag:#04x}"
        )

    # SignedData ::= SEQUENCE {
    #   version             CMSVersion,                INTEGER (0x02)
    #   digestAlgorithms    DigestAlgorithmIdentifiers SET (0x31)
    #   encapContentInfo    EncapsulatedContentInfo    SEQUENCE (0x30)
    #   certificates        [0] IMPLICIT OPTIONAL      (0xA0)
    #   crls                [1] IMPLICIT OPTIONAL      (0xA1)
    #   signerInfos         SignerInfos                SET (0x31)
    # }
    # Walk past each field until we find the signerInfos SET (last
    # element). The first SET we encounter is digestAlgorithms; the
    # final element is always SignerInfos. We track positions so we
    # can find the *last* SET (or one whose offset puts us at the end
    # of SignedData content).
    pos = sd_content
    sd_end = sd_content + sd_len
    signer_infos_offset: int | None = None
    while pos < sd_end:
        tag, length, content = _parse_der_tag(buf, pos)
        next_pos = content + length
        if next_pos == sd_end and tag == 0x31:
            signer_infos_offset = pos
            break
        pos = next_pos
    if signer_infos_offset is None:
        raise ValueError("PKCS#7 SignedData: signerInfos SET not found")

    # ---- 3. SignerInfos SET → first SignerInfo SEQUENCE
    si_set_tag, si_set_len, si_set_content = _parse_der_tag(buf, signer_infos_offset)
    if si_set_tag != 0x31:
        raise ValueError(
            f"PKCS#7 signerInfos: expected SET (0x31), got {si_set_tag:#04x}"
        )
    if si_set_len == 0:
        raise ValueError("PKCS#7 signerInfos: empty SET (no SignerInfo to update)")

    # First SignerInfo SEQUENCE
    si_tag, si_len, si_content = _parse_der_tag(buf, si_set_content)
    if si_tag != 0x30:
        raise ValueError(
            f"PKCS#7 SignerInfo: expected SEQUENCE (0x30), got {si_tag:#04x}"
        )
    si_end = si_content + si_len

    # SignerInfo ::= SEQUENCE {
    #   version            CMSVersion,                  INTEGER  (0x02)
    #   sid                SignerIdentifier,            SEQUENCE / [0]
    #   digestAlgorithm    DigestAlgorithmIdentifier,   SEQUENCE
    #   signedAttrs       [0] IMPLICIT OPTIONAL,        (0xA0)
    #   signatureAlgorithm DigestAlgorithmIdentifier,   SEQUENCE
    #   signature          OCTET STRING,                (0x04)
    #   unsignedAttrs     [1] IMPLICIT OPTIONAL         (0xA1)   ← target
    # }
    # We walk the SignerInfo's children. If we find an existing [1]
    # IMPLICIT SET (unsignedAttrs), we EXTEND it. Otherwise we APPEND
    # a fresh one at the end of SignerInfo.
    new_attr = _build_time_stamp_attribute(bytes(tstoken))

    existing_uattrs_offset: int | None = None
    pos = si_content
    while pos < si_end:
        tag, length, content = _parse_der_tag(buf, pos)
        if tag == 0xA1:
            existing_uattrs_offset = pos
            break
        pos = content + length

    if existing_uattrs_offset is not None:
        # Extend existing [1] IMPLICIT SET OF Attribute.
        ua_tag, ua_len, ua_content = _parse_der_tag(buf, existing_uattrs_offset)
        # New set body = old body + new Attribute.
        new_set_body = buf[ua_content : ua_content + ua_len] + new_attr
        new_uattrs_tlv = _wrap_tlv(0xA1, new_set_body)
        new_si_content = (
            buf[si_content:existing_uattrs_offset]
            + new_uattrs_tlv
            + buf[ua_content + ua_len : si_end]
        )
    else:
        # Append a new [1] IMPLICIT SET OF Attribute at the end of SignerInfo.
        new_uattrs_tlv = _wrap_tlv(0xA1, new_attr)
        new_si_content = buf[si_content:si_end] + new_uattrs_tlv

    # ---- 4. Re-encode lengths bottom-up
    new_signer_info_tlv = _wrap_tlv(0x30, new_si_content)
    # Replace the first SignerInfo in the SignerInfos SET content.
    new_si_set_content = (
        new_signer_info_tlv + buf[si_end : si_set_content + si_set_len]
    )
    new_signer_infos_tlv = _wrap_tlv(0x31, new_si_set_content)

    # Replace the SignerInfos SET in the SignedData SEQUENCE content.
    new_signed_data_content = (
        buf[sd_content:signer_infos_offset] + new_signer_infos_tlv
    )
    new_signed_data_tlv = _wrap_tlv(0x30, new_signed_data_content)

    # Replace the SignedData in the [0] EXPLICIT content.
    new_c0_tlv = _wrap_tlv(0xA0, new_signed_data_tlv)

    # Replace the [0] EXPLICIT in the ContentInfo SEQUENCE content.
    new_ci_content = buf[ci_content:after_oid] + new_c0_tlv
    new_ci_tlv = _wrap_tlv(0x30, new_ci_content)
    return new_ci_tlv


__all__ = [
    "inject_timestamp_token",
]
