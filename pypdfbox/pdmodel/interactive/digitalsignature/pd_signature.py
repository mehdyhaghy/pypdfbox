from __future__ import annotations

import datetime as _dt
import hashlib
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

from .pd_prop_build import PDPropBuild
from .signature_validation_result import SignatureValidationResult

if TYPE_CHECKING:  # pragma: no cover — typing only
    from cryptography.x509 import Certificate

# --------------------------------------------------------------------- DER helpers
#
# Wave 1286: closes the upstream-parity TODO at the bottom of
# :meth:`PDSignature.verify`. The PyCA ``cryptography`` package exposes a
# high-level PKCS#7 *builder* but no high-level *verifier* — full PKCS#7
# signature math (the "signature over signed-attributes" RFC 5652 §5.4
# computation) and chain-trust validation have to be wired by hand
# against ``cryptography.x509`` primitives. The helpers below stay
# private to this module; they are intentionally minimal — just enough
# to find the SignerInfo, recover the signed-attrs blob and verify it.


def _read_der_length(buf: bytes, offset: int) -> tuple[int, int]:
    """Decode a DER length starting at ``offset``. Returns ``(length, n_bytes)``.

    Duplicated from :mod:`.sig_utils` so this module stays
    import-light (sig_utils pulls in the COS layer for unrelated MDP
    helpers). Indefinite-length form (``0x80``) is rejected — DER
    forbids it. Raises :class:`ValueError` on malformed input.
    """
    if offset >= len(buf):
        raise ValueError("DER length: unexpected EOF")
    first = buf[offset]
    if first < 0x80:
        return first, 1
    if first == 0x80:
        raise ValueError("DER forbids indefinite-length form")
    n = first & 0x7F
    if n == 0 or offset + 1 + n > len(buf):
        raise ValueError("DER length: truncated long form")
    length = 0
    for b in buf[offset + 1 : offset + 1 + n]:
        length = (length << 8) | b
    return length, 1 + n


def _read_der_tlv(buf: bytes, offset: int) -> tuple[int, int, int, int]:
    """Read a TLV at ``offset``. Returns ``(tag, header_len, body_offset, body_len)``.

    ``header_len`` is the byte count of tag + length encoding;
    ``body_offset`` = ``offset + header_len``; ``body_len`` is the
    payload length. Total TLV length is ``header_len + body_len``.
    """
    if offset >= len(buf):
        raise ValueError("DER TLV: unexpected EOF")
    tag = buf[offset]
    length, n_bytes = _read_der_length(buf, offset + 1)
    header_len = 1 + n_bytes
    body_offset = offset + header_len
    if body_offset + length > len(buf):
        raise ValueError("DER TLV: body overruns buffer")
    return tag, header_len, body_offset, length


def _walk_signer_info(pkcs7_der: bytes) -> dict[str, bytes] | None:
    """Walk a DER-encoded PKCS#7 / CMS ``SignedData`` blob and return the
    fields needed to verify the signer-info signature.

    Returns a dict with the following bytes-valued keys (all DER-encoded
    fragments / OID payloads / signature bytes), or ``None`` when the
    blob is not shaped like a SignedData with a single SignerInfo:

    - ``signed_attrs_set``: the ``signedAttributes`` value re-encoded as
      a ``SET OF`` (tag ``0x31``) — this is the byte sequence RFC 5652
      §5.4 requires the signature to be verified against.
    - ``signature``: the raw signature OCTET STRING payload.
    - ``digest_algo_oid``: the OID body of the ``digestAlgorithm``.
    - ``signature_algo_oid``: the OID body of the ``signatureAlgorithm``.

    The walker is permissive: any structural mismatch returns ``None``
    instead of raising. Callers treat ``None`` as "couldn't perform full
    PKCS#7 verification" and fall back to the digest-match check.
    """
    try:
        # ContentInfo ::= SEQUENCE { contentType OID, content [0] EXPLICIT … }
        tag, _, body, body_len = _read_der_tlv(pkcs7_der, 0)
        if tag != 0x30:  # SEQUENCE
            return None
        # contentType OID
        oid_tag, _, oid_body, oid_len = _read_der_tlv(pkcs7_der, body)
        if oid_tag != 0x06:
            return None
        # content [0] EXPLICIT
        cursor = oid_body + oid_len
        c_tag, _, c_body, c_len = _read_der_tlv(pkcs7_der, cursor)
        if c_tag != 0xA0:
            return None
        # SignedData SEQUENCE inside
        sd_tag, _, sd_body, sd_len = _read_der_tlv(pkcs7_der, c_body)
        if sd_tag != 0x30:
            return None
        sd_end = sd_body + sd_len
        cursor = sd_body
        # version INTEGER
        v_tag, _, v_body, v_len = _read_der_tlv(pkcs7_der, cursor)
        if v_tag != 0x02:
            return None
        cursor = v_body + v_len
        # digestAlgorithms SET OF AlgorithmIdentifier
        da_tag, _, da_body, da_len = _read_der_tlv(pkcs7_der, cursor)
        if da_tag != 0x31:
            return None
        cursor = da_body + da_len
        # encapContentInfo SEQUENCE
        eci_tag, _, eci_body, eci_len = _read_der_tlv(pkcs7_der, cursor)
        if eci_tag != 0x30:
            return None
        cursor = eci_body + eci_len
        # OPTIONAL: certificates [0] IMPLICIT, crls [1] IMPLICIT
        while cursor < sd_end:
            peek_tag = pkcs7_der[cursor]
            if peek_tag in (0xA0, 0xA1):
                _, _, opt_body, opt_len = _read_der_tlv(pkcs7_der, cursor)
                cursor = opt_body + opt_len
                continue
            if peek_tag == 0x31:
                break  # signerInfos SET
            return None
        # signerInfos SET OF SignerInfo
        if cursor >= sd_end or pkcs7_der[cursor] != 0x31:
            return None
        si_tag, _, si_body, si_len = _read_der_tlv(pkcs7_der, cursor)
        # Take the first SignerInfo (PDF signatures carry exactly one).
        first_tag, _, first_body, first_len = _read_der_tlv(pkcs7_der, si_body)
        if first_tag != 0x30:
            return None
        first_end = first_body + first_len
        cursor = first_body
        # version INTEGER
        sv_tag, _, sv_body, sv_len = _read_der_tlv(pkcs7_der, cursor)
        if sv_tag != 0x02:
            return None
        cursor = sv_body + sv_len
        # sid: SignerIdentifier — IssuerAndSerialNumber (SEQUENCE 0x30) or
        # subjectKeyIdentifier (tagged [0] IMPLICIT, 0x80). Skip its TLV.
        _sid_tag, _, sid_body, sid_len = _read_der_tlv(pkcs7_der, cursor)
        cursor = sid_body + sid_len
        # digestAlgorithm AlgorithmIdentifier ::= SEQUENCE { OID, params }
        diga_tag, _, diga_body, diga_len = _read_der_tlv(pkcs7_der, cursor)
        if diga_tag != 0x30:
            return None
        diga_oid_tag, _, diga_oid_body, diga_oid_len = _read_der_tlv(
            pkcs7_der, diga_body
        )
        if diga_oid_tag != 0x06:
            return None
        digest_algo_oid = pkcs7_der[diga_oid_body : diga_oid_body + diga_oid_len]
        cursor = diga_body + diga_len
        # OPTIONAL: signedAttrs [0] IMPLICIT SET OF Attribute
        signed_attrs_set: bytes | None = None
        if cursor < first_end and pkcs7_der[cursor] == 0xA0:
            sa_tag, _, sa_body, sa_len = _read_der_tlv(pkcs7_der, cursor)
            # Re-encode as ``SET OF`` (0x31) per RFC 5652 §5.4: signature
            # is computed over the SET-tagged DER, not the IMPLICIT tag.
            # We rebuild the length encoding ourselves to mirror DER's
            # short/long-form rules — copying the original header would
            # only work for short-form lengths.
            payload = pkcs7_der[sa_body : sa_body + sa_len]
            signed_attrs_set = b"\x31" + _encode_der_length(sa_len) + payload
            cursor = sa_body + sa_len
        # signatureAlgorithm
        siga_tag, _, siga_body, siga_len = _read_der_tlv(pkcs7_der, cursor)
        if siga_tag != 0x30:
            return None
        siga_oid_tag, _, siga_oid_body, siga_oid_len = _read_der_tlv(
            pkcs7_der, siga_body
        )
        if siga_oid_tag != 0x06:
            return None
        signature_algo_oid = pkcs7_der[siga_oid_body : siga_oid_body + siga_oid_len]
        cursor = siga_body + siga_len
        # signature OCTET STRING
        sig_tag, _, sig_body, sig_len = _read_der_tlv(pkcs7_der, cursor)
        if sig_tag != 0x04:
            return None
        signature = pkcs7_der[sig_body : sig_body + sig_len]

        if signed_attrs_set is None:
            return None
        return {
            "signed_attrs_set": signed_attrs_set,
            "signature": signature,
            "digest_algo_oid": digest_algo_oid,
            "signature_algo_oid": signature_algo_oid,
        }
    except (ValueError, IndexError):
        return None


def _encode_der_length(length: int) -> bytes:
    """Encode ``length`` in DER short/long form."""
    if length < 0:
        raise ValueError("DER length must be non-negative")
    if length < 0x80:
        return bytes([length])
    body: list[int] = []
    n = length
    while n:
        body.insert(0, n & 0xFF)
        n >>= 8
    if len(body) > 0x7F:
        raise ValueError("DER length too large to encode")
    return bytes([0x80 | len(body), *body])


# Map digest-algorithm OIDs (RFC 5754 / RFC 8017) to PyCA hash objects.
# We only enumerate the algorithms PDF signatures use in practice (SHA-1
# through SHA-512). Anything else returns ``None`` from
# :func:`_hash_for_oid` and the signature-math step bails out.
# Note: OIDs below are the *DER bodies* (without the leading tag/length).
_DIGEST_OID_HEX_TO_HASH: dict[str, str] = {
    "2b0e03021a": "SHA1",  # 1.3.14.3.2.26
    "608648016503040201": "SHA256",  # 2.16.840.1.101.3.4.2.1
    "608648016503040202": "SHA384",  # 2.16.840.1.101.3.4.2.2
    "608648016503040203": "SHA512",  # 2.16.840.1.101.3.4.2.3
    "608648016503040204": "SHA224",  # 2.16.840.1.101.3.4.2.4
}


def _hash_for_oid(oid_body: bytes) -> object | None:
    """Look up a PyCA ``hashes.HashAlgorithm`` instance for an OID body."""
    try:
        from cryptography.hazmat.primitives import hashes
    except ImportError:  # pragma: no cover — install-time guard
        return None
    name = _DIGEST_OID_HEX_TO_HASH.get(oid_body.hex())
    if name is None:
        return None
    return getattr(hashes, name)()


def _verify_signed_attrs_signature(
    certificate: Certificate,
    signed_attrs_set_der: bytes,
    signature: bytes,
    digest_algo_oid: bytes,
    signature_algo_oid: bytes,
) -> tuple[bool, str | None]:
    """Verify ``signature`` against ``signed_attrs_set_der`` using
    ``certificate.public_key()``.

    Returns ``(ok, error_message)``. ``ok`` is ``True`` iff the
    signature math passes; ``error_message`` is ``None`` on success or a
    short diagnostic on failure / unsupported algorithm.
    """
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    except ImportError:  # pragma: no cover — install-time guard
        return False, "cryptography is required for PKCS#7 verification"

    digest_hash = _hash_for_oid(digest_algo_oid)
    if digest_hash is None:
        return False, f"unsupported digest algorithm OID {digest_algo_oid.hex()}"

    public_key = certificate.public_key()

    # RSA: the signatureAlgorithm OID can be either
    #   1.2.840.113549.1.1.1 (rsaEncryption — "raw" RSA, PKCS#1 v1.5 with
    #     the digest algorithm taken from ``digestAlgorithm``), or
    #   1.2.840.113549.1.1.{5,11,12,13,14} (RSA-with-SHA1/256/384/512/224
    #     — PKCS#1 v1.5 with digest baked into the OID).
    # In both cases we verify with PKCS#1 v1.5 padding plus ``digest_hash``.
    rsa_oid_hex_prefix = "2a864886f70d0101"  # 1.2.840.113549.1.1
    ec_oid_hex_prefix = "2a8648ce3d04"  # 1.2.840.10045.4 (ECDSA)
    sig_oid_hex = signature_algo_oid.hex()

    try:
        if isinstance(public_key, rsa.RSAPublicKey) and sig_oid_hex.startswith(
            rsa_oid_hex_prefix
        ):
            public_key.verify(
                signature,
                signed_attrs_set_der,
                padding.PKCS1v15(),
                digest_hash,  # type: ignore[arg-type]
            )
            return True, None
        if isinstance(
            public_key, ec.EllipticCurvePublicKey
        ) and sig_oid_hex.startswith(ec_oid_hex_prefix):
            public_key.verify(
                signature,
                signed_attrs_set_der,
                ec.ECDSA(digest_hash),  # type: ignore[arg-type]
            )
            return True, None
    except InvalidSignature:
        return False, "signature math over signed-attributes failed"
    except (ValueError, TypeError) as exc:
        return False, f"signature verification raised: {exc}"

    return False, (
        f"unsupported signature algorithm: key={type(public_key).__name__} "
        f"oid={sig_oid_hex}"
    )


def _verify_chain_trust(
    signer_certificate: Certificate,
    embedded_certs: list[Certificate],
    trust_roots: list[Certificate],
) -> tuple[bool, str | None]:
    """Walk from ``signer_certificate`` up to a member of ``trust_roots``.

    Implementation note: ``cryptography.x509.verification.PolicyBuilder``
    exposes only ``ServerVerifier`` / ``ClientVerifier`` builders (TLS
    server / client name binding), which are inappropriate for PDF
    document-signing chains (no DNS / IP / email subject alternative
    name to bind against). We therefore do a structural walk by hand:
    follow ``issuer``-name chains, verify each non-self-signed link's
    signature with the issuer's public key, and stop when the current
    cert is signed by a member of ``trust_roots``.

    Caller passes an explicit list of trusted root certs — there is no
    implicit system-store lookup (system stores vary by platform and
    pulling them in would require ``certifi`` / ``truststore`` deps).
    Use the empty-list shortcut when no chain trust is wanted.

    Returns ``(ok, error_message)``.
    """
    if not trust_roots:
        return False, "no trust roots supplied — chain trust skipped"

    # Build an issuer-name → cert index covering embedded + roots.
    intermediates: dict[bytes, Certificate] = {}
    for c in (*embedded_certs, *trust_roots):
        intermediates[c.subject.public_bytes()] = c
    root_subjects = {r.subject.public_bytes() for r in trust_roots}

    current = signer_certificate
    # Walk at most len(intermediates)+1 steps to avoid pathological loops.
    for _ in range(len(intermediates) + 1):
        issuer_name = current.issuer.public_bytes()
        # Self-signed: only trusted if it IS one of the roots.
        if issuer_name == current.subject.public_bytes():
            if issuer_name in root_subjects:
                # Verify self-signature for completeness.
                ok, _ = _verify_cert_signature(current, current)
                return (True, None) if ok else (
                    False,
                    "self-signed root failed self-verify",
                )
            return False, "chain terminates at untrusted self-signed cert"
        issuer = intermediates.get(issuer_name)
        if issuer is None:
            return False, "chain broken: missing issuer for " + (
                current.subject.rfc4514_string()
            )
        ok, err = _verify_cert_signature(current, issuer)
        if not ok:
            return False, err or "issuer signature check failed"
        if issuer_name in root_subjects:
            return True, None
        current = issuer
    return False, "chain too long / loop detected"


def _verify_cert_signature(
    cert: Certificate, issuer: Certificate
) -> tuple[bool, str | None]:
    """Verify ``cert.signature`` against ``issuer.public_key()``."""
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa
    except ImportError:  # pragma: no cover — install-time guard
        return False, "cryptography is required"
    try:
        sig_hash = cert.signature_hash_algorithm
        if sig_hash is None:
            return False, "certificate has no signature hash algorithm"
        public_key = issuer.public_key()
        if isinstance(public_key, rsa.RSAPublicKey):
            public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                padding.PKCS1v15(),
                sig_hash,
            )
            return True, None
        if isinstance(public_key, ec.EllipticCurvePublicKey):
            public_key.verify(
                cert.signature,
                cert.tbs_certificate_bytes,
                ec.ECDSA(sig_hash),
            )
            return True, None
    except InvalidSignature:
        return False, "issuer signature is invalid"
    except (ValueError, TypeError) as exc:
        return False, f"chain verification raised: {exc}"
    return False, f"unsupported issuer key type: {type(public_key).__name__}"


_TYPE: COSName = COSName.TYPE  # type: ignore[attr-defined]
_SIG: COSName = COSName.get_pdf_name("Sig")
_FILTER: COSName = COSName.get_pdf_name("Filter")
_SUB_FILTER: COSName = COSName.get_pdf_name("SubFilter")
_NAME: COSName = COSName.get_pdf_name("Name")
_LOCATION: COSName = COSName.get_pdf_name("Location")
_REASON: COSName = COSName.get_pdf_name("Reason")
_CONTACT_INFO: COSName = COSName.get_pdf_name("ContactInfo")
_M: COSName = COSName.get_pdf_name("M")
_BYTE_RANGE: COSName = COSName.get_pdf_name("ByteRange")
_CONTENTS: COSName = COSName.get_pdf_name("Contents")
_CERT: COSName = COSName.get_pdf_name("Cert")
_PROP_BUILD: COSName = COSName.get_pdf_name("Prop_Build")


class PDSignature:
    """Signature value dictionary (``/Type /Sig``). Mirrors PDFBox
    ``PDSignature`` lite surface (PDF 32000-1 §12.8.1, Table 252).

    Deferred upstream behavior: structured ``Calendar`` / ``datetime``
    conversion for ``/M`` is not implemented (raw PDF date strings only),
    actual signing/verification (``/Contents`` placeholder population,
    PKCS#7 generation) is out of scope for this lite port.
    """

    TYPE = "Sig"
    #: ``/Type`` value used for an RFC 3161 document-timestamp signature
    #: (PDF 32000-2 §12.8.5). Distinct from a regular ``/Sig`` signature in
    #: that no signer is asserted — only a trusted-time anchor.
    TYPE_DOC_TIME_STAMP = "DocTimeStamp"

    # /Filter values (PDF 32000-1 Table 252). Upstream exposes these as
    # ``COSName`` constants; we expose plain strings since the snake_case
    # accessors (``set_filter`` / ``get_filter``) operate on names-as-strings.
    FILTER_ADOBE_PPKLITE = "Adobe.PPKLite"
    FILTER_ENTRUST_PPKEF = "Entrust.PPKEF"
    FILTER_CICI_SIGNIT = "CICI.SignIt"
    FILTER_VERISIGN_PPKVS = "VeriSign.PPKVS"

    # /SubFilter values (PDF 32000-1 Table 252).
    SUBFILTER_ADBE_X509_RSA_SHA1 = "adbe.x509.rsa_sha1"
    SUBFILTER_ADBE_PKCS7_DETACHED = "adbe.pkcs7.detached"
    SUBFILTER_ETSI_CADES_DETACHED = "ETSI.CAdES.detached"
    SUBFILTER_ADBE_PKCS7_SHA1 = "adbe.pkcs7.sha1"
    #: ETSI RFC 3161 document timestamp SubFilter (PDF 32000-2 §12.8.5).
    SUBFILTER_ETSI_RFC3161 = "ETSI.RFC3161"

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _SIG)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Type ----------

    def get_type(self) -> str | None:
        """Return ``/Type``. Always ``"Sig"`` for a fresh signature; upstream
        keeps a getter for parity with ``COSObjectable``-style introspection.
        """
        return self._dict.get_name(_TYPE)

    def set_type(self, type_name: str | None) -> None:
        """Set ``/Type``. Mirrors PDFBox's deprecated setter — kept for
        parity. Pass ``None`` to remove (rarely useful — the spec requires
        ``/Type /Sig`` on a signature dictionary).
        """
        if type_name is None:
            self._dict.remove_item(_TYPE)
            return
        self._dict.set_name(_TYPE, type_name)

    # ---------- /Filter ----------

    def get_filter(self) -> str | None:
        # Upstream uses getNameAsString — accept either a name or a string,
        # to be permissive with non-conformant writers that store /Filter
        # as a COSString instead of a COSName.
        return self._dict.get_string(_FILTER)

    def set_filter(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_FILTER)
            return
        self._dict.set_name(_FILTER, name)

    # ---------- /SubFilter ----------

    def get_sub_filter(self) -> str | None:
        # Upstream uses getNameAsString — see ``get_filter`` for rationale.
        return self._dict.get_string(_SUB_FILTER)

    def set_sub_filter(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_SUB_FILTER)
            return
        self._dict.set_name(_SUB_FILTER, name)

    # ---------- /Name ----------

    def get_name(self) -> str | None:
        return self._dict.get_string(_NAME)

    def set_name(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_NAME)
            return
        self._dict.set_string(_NAME, name)

    # ---------- /Location ----------

    def get_location(self) -> str | None:
        return self._dict.get_string(_LOCATION)

    def set_location(self, location: str | None) -> None:
        if location is None:
            self._dict.remove_item(_LOCATION)
            return
        self._dict.set_string(_LOCATION, location)

    # ---------- /Reason ----------

    def get_reason(self) -> str | None:
        return self._dict.get_string(_REASON)

    def set_reason(self, reason: str | None) -> None:
        if reason is None:
            self._dict.remove_item(_REASON)
            return
        self._dict.set_string(_REASON, reason)

    # ---------- /ContactInfo ----------

    def get_contact_info(self) -> str | None:
        return self._dict.get_string(_CONTACT_INFO)

    def set_contact_info(self, contact_info: str | None) -> None:
        if contact_info is None:
            self._dict.remove_item(_CONTACT_INFO)
            return
        self._dict.set_string(_CONTACT_INFO, contact_info)

    # ---------- /M sign date ----------

    def get_sign_date(self) -> str | None:
        return self._dict.get_string(_M)

    def set_sign_date(self, sign_date: str | None) -> None:
        if sign_date is None:
            self._dict.remove_item(_M)
            return
        self._dict.set_string(_M, sign_date)

    def get_sign_date_as_datetime(self) -> _dt.datetime | None:
        """Return ``/M`` parsed as a timezone-aware :class:`datetime`.

        Mirrors upstream ``getSignDate(): Calendar`` parity. Returns ``None``
        if ``/M`` is absent or unparseable. The lite port stores ``/M`` as a
        raw PDF date string (``D:YYYYMMDDHHmmSSOHH'mm'``) — this typed
        accessor reuses ``PDDocumentInformation``'s parser.
        """
        raw = self.get_sign_date()
        if raw is None:
            return None
        from pypdfbox.pdmodel.pd_document_information import _parse_pdf_date

        return _parse_pdf_date(raw)

    def set_sign_date_as_datetime(self, value: _dt.datetime | None) -> None:
        """Store ``/M`` as a PDF date string from a :class:`datetime`.

        Mirrors upstream ``setSignDate(Calendar)``. Naive datetimes are
        treated as UTC.
        """
        if value is None:
            self._dict.remove_item(_M)
            return
        from pypdfbox.pdmodel.pd_document_information import _format_pdf_date

        self._dict.set_string(_M, _format_pdf_date(value))

    # ---------- /ByteRange ----------

    def get_byte_range(self) -> list[int] | None:
        v = self._dict.get_dictionary_object(_BYTE_RANGE)
        if not isinstance(v, COSArray):
            return None
        ints = v.to_cos_number_integer_list()
        if any(i is None for i in ints):
            return None
        return [int(i) for i in ints]  # type: ignore[arg-type]

    def set_byte_range(self, byte_range: list[int] | None) -> None:
        if byte_range is None:
            self._dict.remove_item(_BYTE_RANGE)
            return
        if len(byte_range) != 4:
            raise ValueError(
                f"ByteRange must have exactly 4 entries, got {len(byte_range)}"
            )
        self._dict.set_item(_BYTE_RANGE, COSArray.of_cos_integers(byte_range))

    # ---------- /Contents ----------

    def get_contents(self) -> bytes | None:
        v = self._dict.get_dictionary_object(_CONTENTS)
        if isinstance(v, COSString):
            return v.get_bytes()
        return None

    def set_contents(self, contents: bytes | None) -> None:
        if contents is None:
            self._dict.remove_item(_CONTENTS)
            return
        s = COSString(contents)
        s.set_force_hex_form(True)
        self._dict.set_item(_CONTENTS, s)

    # ---------- /Cert ----------

    def get_cert(self) -> list[str] | None:
        """Return the ``/Cert`` entry as a list of certificate strings.

        ``/Cert`` is used by the ``adbe.x509.rsa_sha1`` SubFilter to carry
        either a single DER-encoded certificate (as a COSString) or an
        array of certificates (each a COSString). Always returned as a
        list of strings on read regardless of single-vs-array storage,
        matching PDFBox's ``getCertString`` parity behavior. Returns
        ``None`` when ``/Cert`` is absent.
        """
        v = self._dict.get_dictionary_object(_CERT)
        if isinstance(v, COSString):
            s = v.get_string()
            return [s] if s is not None else None
        if isinstance(v, COSArray):
            certs = v.to_cos_string_string_list()
            return [c for c in certs if c is not None]
        return None

    def set_cert(self, cert: str | list[str] | None) -> None:
        """Set the ``/Cert`` entry.

        Pass a single ``str`` to write a COSString, a list to write a
        COSArray of COSStrings, or ``None`` to remove the entry.
        """
        if cert is None:
            self._dict.remove_item(_CERT)
            return
        if isinstance(cert, str):
            self._dict.set_string(_CERT, cert)
            return
        self._dict.set_item(_CERT, COSArray.of_cos_strings(cert))

    # ---------- /Prop_Build ----------

    def get_prop_build(self) -> PDPropBuild | None:
        """PDF signature build dictionary. Provides information about the
        signature handler that was used to create this signature.
        """
        v = self._dict.get_dictionary_object(_PROP_BUILD)
        if isinstance(v, COSDictionary):
            return PDPropBuild(v)
        return None

    def set_prop_build(self, prop_build: PDPropBuild | None) -> None:
        """Set the PDF signature build dictionary."""
        if prop_build is None:
            self._dict.remove_item(_PROP_BUILD)
            return
        self._dict.set_item(_PROP_BUILD, prop_build.get_cos_object())

    def get_converted_contents(self, raw: bytes | None) -> bytes:
        """Mirror upstream private ``PDSignature.getConvertedContents``
        (lines 363-388 in PDSignature.java).

        Strips the optional PDF-string delimiters (``<`` / ``(`` at the
        start, ``>`` / ``)`` at the end) from the raw bytes and decodes
        the resulting hex pairs into the binary PKCS#7 SignedData blob.

        Surfaced publicly here because pypdfbox does not have Java's
        package-private visibility — callers reading the encoded
        ``/Contents`` form (e.g. from a custom ``ByteRange`` extractor)
        need the same hex-strip + parse step. Returns ``b""`` for an
        empty / ``None`` input.
        """
        if not raw:
            return b""
        start = 0
        end = len(raw)
        # Strip leading "<" or "(" (Java PDF-string delimiters).
        if raw[0:1] in (b"<", b"("):
            start = 1
        # Strip trailing ">" or ")".
        if end > start and raw[end - 1 : end] in (b">", b")"):
            end -= 1
        body = raw[start:end]
        # Java decodes via COSString.parseHex on a Latin-1 string — pypdfbox
        # ports that helper as :meth:`COSString.parse_hex` which expects a
        # ``str``. Decode the body as ISO-8859-1 (matching upstream's
        # ``new String(buffer, ISO_8859_1)``) and let parse_hex do the
        # hex-pair-to-bytes conversion.
        return COSString.parse_hex(body.decode("iso-8859-1")).get_bytes()

    # ---------- convenience: raw /Contents and signed bytes ----------

    def get_contents_bytes(self) -> bytes | None:
        """Return the raw decoded ``/Contents`` PKCS#7 SignedData blob.

        Alias of :meth:`get_contents` — kept for symmetry with
        :meth:`get_signed_data` which returns the *bytes that were signed*
        rather than the *signature* bytes themselves.
        """
        return self.get_contents()

    def get_signed_data(self, document_bytes: bytes) -> bytes | None:
        """Return the concatenated byte slices identified by ``/ByteRange``.

        ``/ByteRange`` is ``[start1, len1, start2, len2]``: the two ranges
        that bracket the ``/Contents`` placeholder. Hashing this byte string
        is what produces the message digest covered by the PKCS#7 signature.
        Returns ``None`` if no ``/ByteRange`` is present or if the stored
        ranges are malformed for ``document_bytes``.
        """
        br = self.get_byte_range()
        if br is None:
            return None
        if len(br) != 4:
            return None
        start1, len1, start2, len2 = br
        document_len = len(document_bytes)
        for start, length in ((start1, len1), (start2, len2)):
            if start < 0 or length < 0:
                return None
            if start > document_len or start + length > document_len:
                return None
        return document_bytes[start1 : start1 + len1] + document_bytes[start2 : start2 + len2]

    def get_signed_content(self, pdf_file: bytes) -> bytes:
        """Return the bytes of ``pdf_file`` covered by ``/ByteRange``.

        Mirrors upstream ``PDSignature.getSignedContent(byte[])``. This is
        the byte sequence the signature is computed over — i.e. the PDF
        with the ``/Contents`` hex placeholder excised.

        Raises :class:`IndexError` if ``/ByteRange`` is absent or malformed
        (parity with upstream's ``IndexOutOfBoundsException`` contract).
        """
        signed = self.get_signed_data(pdf_file)
        if signed is None:
            raise IndexError("missing or malformed /ByteRange")
        return signed

    # ---------- verify ----------

    def verify(
        self,
        document_bytes: bytes,
        *,
        trust_roots: list[Certificate] | None = None,
    ) -> SignatureValidationResult:
        """Verify this signature against ``document_bytes``.

        Wave 1286 brings the signature pipeline to feature-parity with
        the upstream PDFBox lite verifier:

        1. Computes the document digest over the ``/ByteRange`` slices.
        2. Extracts the signer certificate from the PKCS#7 ``/Contents``
           blob via :func:`cryptography.hazmat.primitives.serialization.
           pkcs7.load_der_pkcs7_certificates`.
        3. Recovers the ``messageDigest`` signed-attribute (OID
           ``1.2.840.113549.1.9.4``) and compares it with the digest of
           the bracketed bytes — a match proves the document was not
           altered after signing.
        4. **(new)** Verifies the SignerInfo *signature* over the DER
           encoding of the ``SET OF`` signed-attributes (RFC 5652 §5.4)
           — i.e. the math that proves the SignerInfo came from the
           holder of the private key matching the signer certificate.
        5. **(new)** If ``trust_roots`` is supplied, walks the issuer
           chain from the signer cert through the embedded certs up to
           a trusted root and verifies each link's signature.

        :param document_bytes: full byte content of the PDF being
            verified — :meth:`get_signed_data` bracketed-byte extraction
            runs against this.
        :param trust_roots: explicit list of :class:`Certificate` objects
            to anchor the chain walk against. The empty list (or
            ``None``) skips chain trust; :attr:`is_valid` then reflects
            only digest-match + signed-attrs signature math.

        :returns: a :class:`SignatureValidationResult` whose
            :attr:`is_valid` is ``True`` iff every available check
            passed. ``errors`` carries a short diagnostic per failed
            check. Best-effort: an unsupported algorithm or malformed
            blob never raises — it returns ``is_valid=False`` with the
            diagnostic appended.
        """
        result = SignatureValidationResult()

        byte_range = self.get_byte_range()
        if byte_range is None:
            result.errors.append("missing /ByteRange")
            return result
        if len(byte_range) != 4:
            result.errors.append(
                f"/ByteRange must have 4 entries, got {len(byte_range)}"
            )
            return result

        contents = self.get_contents_bytes()
        if contents is None:
            result.errors.append("missing /Contents")
            return result

        # Compute digest over /ByteRange slices.
        signed_data = self.get_signed_data(document_bytes)
        if signed_data is None:
            result.errors.append("could not extract signed data from document")
            return result

        sub_filter = (self.get_sub_filter() or "").lower()
        if sub_filter == "adbe.pkcs7.sha1":
            result.computed_digest = hashlib.sha1(signed_data).digest()  # noqa: S324
        else:
            result.computed_digest = hashlib.sha256(signed_data).digest()

        # Extract signer certificate from embedded PKCS#7 SignedData blob.
        try:
            from cryptography.hazmat.primitives.serialization import pkcs7
        except ImportError as exc:  # pragma: no cover — install-time guard
            result.errors.append(
                f"cryptography is required for PKCS#7 verification: {exc}"
            )
            return result

        # Strip trailing NUL padding — PDF writers commonly zero-pad the
        # /Contents hex string up to the placeholder width, leaving the
        # actual DER blob followed by ``\x00`` bytes. ``cryptography``
        # otherwise emits a "ParseError: ExtraData" BER warning.
        trimmed = contents.rstrip(b"\x00")

        try:
            certs = pkcs7.load_der_pkcs7_certificates(trimmed)
        except Exception as exc:  # noqa: BLE001 — surface any parse failure
            result.errors.append(f"failed to parse PKCS#7 /Contents: {exc}")
            return result

        if not certs:
            result.errors.append("no certificates in PKCS#7 SignedData")
            return result

        cert = certs[0]
        result.signer_certificate = cert
        try:
            result.signer_subject = cert.subject.rfc4514_string()
        except Exception:  # noqa: BLE001
            result.signer_subject = None
        try:
            result.signer_serial_number = int(cert.serial_number)
        except Exception:  # noqa: BLE001
            result.signer_serial_number = None

        # Recover the messageDigest signed-attribute from the SignedData
        # blob — minimal hand-rolled DER walker (we deliberately do not
        # depend on asn1crypto; see CHANGES.md). Returns ``None`` if the
        # blob is malformed or missing the attribute.
        from .sig_utils import extract_pkcs7_message_digest

        try:
            result.signed_digest = extract_pkcs7_message_digest(trimmed)
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"failed to recover messageDigest: {exc}")
            result.signed_digest = None

        # Digest-match check. A pass here means the bracketed bytes were
        # not altered after signing — NOT that the signer cert is trusted.
        digest_match: bool
        if result.signed_digest is not None and result.computed_digest is not None:
            digest_match = result.signed_digest == result.computed_digest
            if not digest_match:
                result.errors.append(
                    "digest mismatch: messageDigest signed-attribute does "
                    "not match recomputed /ByteRange digest"
                )
        else:
            digest_match = False
            result.errors.append(
                "messageDigest signed-attribute not found in PKCS#7 — "
                "cannot perform digest-match check"
            )

        # Wave 1286: signature math over the signed-attributes (RFC 5652
        # §5.4). The PyCA ``cryptography`` package's high-level pkcs7 API
        # is signing-only, so we walk the SignedData DER ourselves to
        # recover the SignerInfo fields and feed them into the public
        # key's low-level ``verify`` primitive.
        signer_info = _walk_signer_info(trimmed)
        sig_math_ok: bool
        if signer_info is None:
            sig_math_ok = False
            result.errors.append(
                "could not locate SignerInfo signed-attributes; full "
                "PKCS#7 signature math skipped"
            )
        else:
            sig_math_ok, sig_err = _verify_signed_attrs_signature(
                cert,
                signer_info["signed_attrs_set"],
                signer_info["signature"],
                signer_info["digest_algo_oid"],
                signer_info["signature_algo_oid"],
            )
            if sig_err is not None:
                result.errors.append(sig_err)

        # Wave 1286: optional chain-trust walk. When the caller passes
        # ``trust_roots=None`` (or an empty list) we keep the upstream
        # behaviour of "digest + signature math = valid"; with an
        # explicit trust anchor we additionally require the chain to
        # reach it.
        chain_ok: bool
        if trust_roots is None or not trust_roots:
            chain_ok = True
        else:
            chain_ok, chain_err = _verify_chain_trust(
                cert,
                certs[1:],
                list(trust_roots),
            )
            if chain_err is not None:
                result.errors.append(chain_err)

        result.is_valid = digest_match and sig_math_ok and chain_ok
        return result

    # ---------- presence predicates ----------

    def has_filter(self) -> bool:
        """Return ``True`` if ``/Filter`` is present."""
        return self._dict.contains_key(_FILTER)

    def has_sub_filter(self) -> bool:
        """Return ``True`` if ``/SubFilter`` is present."""
        return self._dict.contains_key(_SUB_FILTER)

    def has_byte_range(self) -> bool:
        """Return ``True`` if ``/ByteRange`` is present."""
        return self._dict.contains_key(_BYTE_RANGE)

    def has_contents(self) -> bool:
        """Return ``True`` if ``/Contents`` is present."""
        return self._dict.contains_key(_CONTENTS)

    def has_cert(self) -> bool:
        """Return ``True`` if ``/Cert`` is present."""
        return self._dict.contains_key(_CERT)

    def has_prop_build(self) -> bool:
        """Return ``True`` if ``/Prop_Build`` is present."""
        return self._dict.contains_key(_PROP_BUILD)

    def has_sign_date(self) -> bool:
        """Return ``True`` if ``/M`` (sign date) is present."""
        return self._dict.contains_key(_M)

    def has_name(self) -> bool:
        """Return ``True`` if ``/Name`` is present."""
        return self._dict.contains_key(_NAME)

    def has_reason(self) -> bool:
        """Return ``True`` if ``/Reason`` is present."""
        return self._dict.contains_key(_REASON)

    def has_location(self) -> bool:
        """Return ``True`` if ``/Location`` is present."""
        return self._dict.contains_key(_LOCATION)

    def has_contact_info(self) -> bool:
        """Return ``True`` if ``/ContactInfo`` is present."""
        return self._dict.contains_key(_CONTACT_INFO)

    # ---------- /Type predicates ----------

    def is_doc_time_stamp(self) -> bool:
        """Return ``True`` if this is an RFC 3161 document timestamp.

        A document timestamp has ``/Type /DocTimeStamp`` (PDF 32000-2
        §12.8.5) instead of the usual ``/Type /Sig``. Most callers want
        to disambiguate signer-attesting signatures from timestamp-only
        anchors when iterating ``PDDocument.get_signature_dictionaries``.
        """
        return self.get_type() == self.TYPE_DOC_TIME_STAMP

    def is_signature(self) -> bool:
        """Return ``True`` if this is a regular ``/Type /Sig`` signature
        (i.e. *not* a ``/DocTimeStamp``)."""
        return self.get_type() == self.TYPE

    # ---------- /SubFilter predicates ----------

    def is_pkcs7_detached(self) -> bool:
        """Return ``True`` if ``/SubFilter`` is ``adbe.pkcs7.detached``
        (the default modern signature encoding)."""
        return self.get_sub_filter() == self.SUBFILTER_ADBE_PKCS7_DETACHED

    def is_pkcs7_sha1(self) -> bool:
        """Return ``True`` if ``/SubFilter`` is ``adbe.pkcs7.sha1``
        (legacy SHA-1-only encoding)."""
        return self.get_sub_filter() == self.SUBFILTER_ADBE_PKCS7_SHA1

    def is_x509_rsa_sha1(self) -> bool:
        """Return ``True`` if ``/SubFilter`` is ``adbe.x509.rsa_sha1``
        (uses ``/Cert`` for the certificate chain)."""
        return self.get_sub_filter() == self.SUBFILTER_ADBE_X509_RSA_SHA1

    def is_etsi_cades_detached(self) -> bool:
        """Return ``True`` if ``/SubFilter`` is ``ETSI.CAdES.detached``
        (PAdES, PDF 32000-2 §12.8.3.4)."""
        return self.get_sub_filter() == self.SUBFILTER_ETSI_CADES_DETACHED

    def is_etsi_rfc3161(self) -> bool:
        """Return ``True`` if ``/SubFilter`` is ``ETSI.RFC3161``
        (document-timestamp encoding, PDF 32000-2 §12.8.5)."""
        return self.get_sub_filter() == self.SUBFILTER_ETSI_RFC3161

    # ---------- string form ----------

    def __str__(self) -> str:
        """Human-readable summary used by :meth:`PDSignatureField.get_value_as_string`.

        Mirrors upstream behavior of ``PDSignature.toString()`` — Java's default
        ``Object.toString()`` is ``ClassName@hashcode``, which is not useful, so
        the lite port returns a compact key=value summary of the populated
        identity fields (``/Name``, ``/Reason``, ``/Location``, ``/M``,
        ``/ContactInfo``). Empty/absent entries are omitted.
        """
        parts: list[str] = []
        for label, value in (
            ("name", self.get_name()),
            ("reason", self.get_reason()),
            ("location", self.get_location()),
            ("date", self.get_sign_date()),
            ("contact", self.get_contact_info()),
        ):
            if value:
                parts.append(f"{label}={value}")
        body = ", ".join(parts) if parts else "<empty>"
        return f"PDSignature({body})"


__all__ = ["PDPropBuild", "PDSignature", "SignatureValidationResult"]
