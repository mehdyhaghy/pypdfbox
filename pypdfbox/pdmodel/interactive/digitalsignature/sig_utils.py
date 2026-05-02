from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName

from .pd_signature import PDSignature

if TYPE_CHECKING:  # pragma: no cover — typing only
    from cryptography.x509 import Certificate

    from pypdfbox.pdmodel.pd_document import PDDocument


_REFERENCE: COSName = COSName.get_pdf_name("Reference")
_TRANSFORM_METHOD: COSName = COSName.get_pdf_name("TransformMethod")
_TRANSFORM_PARAMS: COSName = COSName.get_pdf_name("TransformParams")
_DOC_MDP: COSName = COSName.get_pdf_name("DocMDP")
_P: COSName = COSName.get_pdf_name("P")
_PERMS: COSName = COSName.get_pdf_name("Perms")
_BYTE_RANGE: COSName = COSName.get_pdf_name("ByteRange")
_CONTENTS: COSName = COSName.get_pdf_name("Contents")
_TYPE: COSName = COSName.get_pdf_name("Type")
_SIG: COSName = COSName.get_pdf_name("Sig")
_DOC_TIME_STAMP: COSName = COSName.get_pdf_name("DocTimeStamp")


# --------------------------------------------------------------------- MDP API


def get_mdp_permission(document: PDDocument) -> int:
    """Get the MDP (Modification Detection and Prevention) permission level.

    Mirrors PDFBox examples ``SigUtils.getMDPPermission``. Returns ``0`` if
    no MDP signature is present, otherwise ``1``, ``2`` or ``3`` (PDF 32000-1
    §12.8.2.2 / Table 257):

    * ``1`` — no changes permitted; any change invalidates the signature.
    * ``2`` — form fill-in and signing allowed; other changes invalidate.
    * ``3`` — also annotation create/delete/modify allowed.

    Looks up ``/Catalog/Perms/DocMDP``, follows its ``/Reference`` array to
    the first ``/TransformMethod /DocMDP`` entry, and reads ``/TransformParams
    /P``. Anything malformed returns ``0`` (no MDP), matching upstream's
    permissive parsing.
    """
    catalog = document.get_document_catalog()
    perms = catalog.get_perms()
    if perms is None:
        return 0
    base = perms.get_dictionary_object(_DOC_MDP)
    if not isinstance(base, COSDictionary):
        return 0
    references = base.get_dictionary_object(_REFERENCE)
    if not isinstance(references, COSArray):
        return 0
    for i in range(len(references)):
        ref = references.get_object(i)
        if not isinstance(ref, COSDictionary):
            continue
        method = ref.get_dictionary_object(_TRANSFORM_METHOD)
        if not (isinstance(method, COSName) and method.get_name() == "DocMDP"):
            continue
        params = ref.get_dictionary_object(_TRANSFORM_PARAMS)
        if not isinstance(params, COSDictionary):
            continue
        p = params.get_dictionary_object(_P)
        if isinstance(p, COSInteger):
            value = int(p.int_value())
            if 1 <= value <= 3:
                return value
        return 0
    return 0


def set_mdp_permission(
    document: PDDocument, signature: PDSignature, access_permissions: int
) -> None:
    """Attach an MDP (Modification Detection and Prevention) transform to
    ``signature`` and wire it into the document catalog at ``/Perms/DocMDP``.

    Mirrors PDFBox examples ``SigUtils.setMDPPermission``. ``access_permissions``
    is one of:

    * ``1`` — no changes permitted.
    * ``2`` — form fill-in / signing allowed.
    * ``3`` — also annotation create/delete/modify allowed.

    Raises :class:`ValueError` for any other value, :class:`ValueError`
    if a DocMDP transform is already present (only one MDP signature per
    document is permitted by the spec), and :class:`ValueError` if any
    non-timestamp approval signature with ``/Contents`` already exists
    on the document — the spec mandates that the certification (DocMDP)
    signature precedes any approval signatures.
    """
    if access_permissions not in (1, 2, 3):
        raise ValueError(
            f"Access permissions must be 1, 2 or 3; got {access_permissions}"
        )

    # Mirror upstream SigUtils.setMDPPermission: reject if a previous
    # non-timestamp approval signature with /Contents already exists.
    for existing in document.get_signature_dictionaries():
        existing_cos = existing.get_cos_object()
        existing_type = existing_cos.get_item(_TYPE)
        # Skip timestamp signatures — only approval signatures conflict.
        if isinstance(existing_type, COSName) and existing_type.get_name() == "DocTimeStamp":
            continue
        if existing_cos.contains_key(_CONTENTS):
            raise ValueError(
                "DocMDP transform method not allowed if an approval signature exists"
            )

    sig_dict = signature.get_cos_object()
    catalog = document.get_document_catalog()

    perms = catalog.get_perms()
    if perms is not None and perms.get_dictionary_object(_DOC_MDP) is not None:
        raise ValueError(
            "DocMDP transform parameters dictionary is already present "
            "in the catalog; only one MDP signature allowed per document"
        )

    transform_params = COSDictionary()
    transform_params.set_item(COSName.TYPE, COSName.get_pdf_name("TransformParams"))  # type: ignore[attr-defined]
    transform_params.set_item(_P, COSInteger.get(access_permissions))
    transform_params.set_item(
        COSName.get_pdf_name("V"), COSName.get_pdf_name("1.2")
    )
    transform_params.set_needs_to_be_updated(True)

    reference = COSDictionary()
    reference.set_item(COSName.TYPE, COSName.get_pdf_name("SigRef"))  # type: ignore[attr-defined]
    reference.set_item(_TRANSFORM_METHOD, COSName.get_pdf_name("DocMDP"))
    reference.set_item(
        COSName.get_pdf_name("DigestMethod"), COSName.get_pdf_name("SHA1")
    )
    reference.set_item(_TRANSFORM_PARAMS, transform_params)
    reference.set_needs_to_be_updated(True)

    reference_array = COSArray()
    reference_array.add(reference)
    sig_dict.set_item(_REFERENCE, reference_array)

    if perms is None:
        perms = COSDictionary()
        catalog.set_perms(perms)
    perms.set_item(_DOC_MDP, sig_dict)
    perms.set_needs_to_be_updated(True)
    catalog.get_cos_object().set_needs_to_be_updated(True)


# ----------------------------------------------------------------- cert checks


def _has_extended_key_usage(cert: Certificate, oid_dotted_string: str) -> bool:
    try:
        from cryptography.x509 import ExtensionNotFound
        from cryptography.x509.oid import ExtensionOID
    except ImportError as exc:  # pragma: no cover — install-time
        raise RuntimeError("cryptography is required for SigUtils") from exc
    try:
        ext = cert.extensions.get_extension_for_oid(
            ExtensionOID.EXTENDED_KEY_USAGE
        )
    except ExtensionNotFound:
        return False
    return any(usage.dotted_string == oid_dotted_string for usage in ext.value)


def check_certificate_usage(certificate: Certificate) -> list[str]:
    """Walk ``certificate`` for the X.509 KeyUsage / ExtendedKeyUsage bits a
    PDF *signing* certificate is supposed to carry.

    Mirrors PDFBox examples ``SigUtils.checkCertificateUsage``. Returns a
    list of warning strings (one per issue) — empty list means the cert
    looks fine for signing. Pure structural check; no chain-trust math.

    Warnings cover:

    * KeyUsage extension missing or marked non-critical.
    * ``digitalSignature`` and ``nonRepudiation`` both clear (need at least
      one for PDF signing).
    * ExtendedKeyUsage present but lacks any of: ``id-kp-emailProtection``
      (1.3.6.1.5.5.7.3.4), ``id-kp-codeSigning`` (1.3.6.1.5.5.7.3.3),
      ``anyExtendedKeyUsage`` (2.5.29.37.0),
      Adobe-Authentic-Documents-Trust (1.2.840.113583.1.1.5),
      or Microsoft document-signing (1.3.6.1.4.1.311.10.3.12 — not in
      Adobe's docs but tolerated in practice). Matches upstream
      ``SigUtils.checkCertificateUsage``.
    """
    warnings: list[str] = []
    try:
        from cryptography.x509 import ExtensionNotFound
        from cryptography.x509.oid import ExtensionOID
    except ImportError as exc:  # pragma: no cover — install-time
        raise RuntimeError("cryptography is required for SigUtils") from exc

    # KeyUsage
    try:
        ku_ext = certificate.extensions.get_extension_for_oid(
            ExtensionOID.KEY_USAGE
        )
    except ExtensionNotFound:
        warnings.append("Certificate has no KeyUsage extension")
    else:
        if not ku_ext.critical:
            warnings.append("KeyUsage extension is not marked critical")
        ku = ku_ext.value
        if not (ku.digital_signature or ku.content_commitment):
            # ``content_commitment`` is the X.509 v3 name for nonRepudiation.
            warnings.append(
                "Certificate KeyUsage lacks digitalSignature / nonRepudiation"
            )

    # ExtendedKeyUsage
    try:
        eku_ext = certificate.extensions.get_extension_for_oid(
            ExtensionOID.EXTENDED_KEY_USAGE
        )
    except ExtensionNotFound:
        return warnings  # EKU is optional.

    eku_oids = {usage.dotted_string for usage in eku_ext.value}
    # 1.3.6.1.5.5.7.3.4   = id-kp-emailProtection
    # 1.3.6.1.5.5.7.3.3   = id-kp-codeSigning
    # 2.5.29.37.0         = anyExtendedKeyUsage
    # 1.2.840.113583.1.1.5 = Adobe Authentic Documents Trust
    # 1.3.6.1.4.1.311.10.3.12 = Microsoft Document Signing (not in Adobe
    #                           docs, tolerated by upstream and Adobe Reader)
    expected = {
        "1.3.6.1.5.5.7.3.4",
        "1.3.6.1.5.5.7.3.3",
        "2.5.29.37.0",
        "1.2.840.113583.1.1.5",
        "1.3.6.1.4.1.311.10.3.12",
    }
    if eku_oids.isdisjoint(expected):
        warnings.append(
            "Certificate ExtendedKeyUsage lacks emailProtection / "
            "codeSigning / anyExtendedKeyUsage / Adobe Authentic "
            "Documents Trust / Microsoft Document Signing"
        )
    return warnings


def check_time_stamp_certificate_usage(certificate: Certificate) -> list[str]:
    """Walk ``certificate`` for the ExtendedKeyUsage a TSA (RFC 3161
    timestamp authority) certificate must carry — namely
    ``id-kp-timeStamping`` (1.3.6.1.5.5.7.3.8).

    Mirrors PDFBox examples ``SigUtils.checkTimeStampCertificateUsage``.
    Returns a list of warnings; empty list means the TSA cert is properly
    marked. If the certificate has no ExtendedKeyUsage extension at all
    no warning is issued, matching upstream's permissive behavior (it
    only logs when EKU is present-but-wrong).
    """
    warnings: list[str] = []
    try:
        from cryptography.x509 import ExtensionNotFound
        from cryptography.x509.oid import ExtensionOID
    except ImportError as exc:  # pragma: no cover — install-time
        raise RuntimeError("cryptography is required for SigUtils") from exc

    try:
        eku_ext = certificate.extensions.get_extension_for_oid(
            ExtensionOID.EXTENDED_KEY_USAGE
        )
    except ExtensionNotFound:
        # Upstream only warns when EKU is present-but-wrong; absence is silent.
        return warnings

    eku_oids = {usage.dotted_string for usage in eku_ext.value}
    if "1.3.6.1.5.5.7.3.8" not in eku_oids:
        warnings.append(
            "TSA certificate ExtendedKeyUsage lacks timeStamping "
            "(1.3.6.1.5.5.7.3.8)"
        )
    return warnings


def check_responder_certificate_usage(certificate: Certificate) -> list[str]:
    """Walk ``certificate`` for the ExtendedKeyUsage an OCSP-responder
    certificate must carry — namely ``id-kp-OCSPSigning`` (1.3.6.1.5.5.7.3.9).

    Mirrors PDFBox examples ``SigUtils.checkResponderCertificateUsage``.
    Returns a list of warnings; empty list means the responder cert is
    properly marked.
    """
    warnings: list[str] = []
    try:
        from cryptography.x509 import ExtensionNotFound
        from cryptography.x509.oid import ExtensionOID
    except ImportError as exc:  # pragma: no cover — install-time
        raise RuntimeError("cryptography is required for SigUtils") from exc

    try:
        eku_ext = certificate.extensions.get_extension_for_oid(
            ExtensionOID.EXTENDED_KEY_USAGE
        )
    except ExtensionNotFound:
        warnings.append(
            "Responder certificate has no ExtendedKeyUsage extension"
        )
        return warnings

    eku_oids = {usage.dotted_string for usage in eku_ext.value}
    if "1.3.6.1.5.5.7.3.9" not in eku_oids:
        warnings.append(
            "Responder certificate ExtendedKeyUsage lacks OCSPSigning "
            "(1.3.6.1.5.5.7.3.9)"
        )
    return warnings


# ------------------------------------------------------------ signature picker


def get_last_relevant_signature(document: PDDocument) -> PDSignature | None:
    """Return the *latest-applied* :class:`PDSignature` in ``document``, or
    ``None`` if there are no signatures.

    Mirrors PDFBox examples ``SigUtils.getLastRelevantSignature``. The
    upstream heuristic is: of all signatures whose ``/ByteRange`` is set,
    pick the one whose second range ends *latest in the file* — i.e. the
    one whose update covers the most bytes. That is the signature applied
    by the most-recent incremental save, and so the one whose lock /
    permission bits are the active ones for the document's current state.

    The picked signature's ``/Type`` must be absent, ``/Sig``, or
    ``/DocTimeStamp``; any other ``/Type`` (e.g. ``/Catalog`` from a bogus
    entry) yields ``None`` to match upstream's filter.
    """
    sigs = document.get_signature_dictionaries()
    if not sigs:
        return None

    best: PDSignature | None = None
    best_end = -1
    for sig in sigs:
        br = sig.get_byte_range()
        if br is None or len(br) != 4:
            continue
        end = int(br[2]) + int(br[3])
        if end > best_end:
            best_end = end
            best = sig
    if best is None:
        # Fallback: no /ByteRange anywhere — pick the final signature in
        # document order so callers still get a usable handle.
        best = sigs[-1]

    # Upstream filters: only return if /Type is absent, /Sig, or /DocTimeStamp.
    type_obj = best.get_cos_object().get_item(_TYPE)
    if type_obj is None:
        return best
    if isinstance(type_obj, COSName) and type_obj.get_name() in (
        "Sig",
        "DocTimeStamp",
    ):
        return best
    return None


# ------------------------------------------------------------- /ByteRange helpers


def compute_byte_range(
    document_bytes: bytes | bytearray, contents_open: int, contents_close: int
) -> list[int]:
    """Compute the four-tuple ``[start1, len1, start2, len2]`` for a
    ``/Contents <…>`` placeholder located at ``contents_open`` (the ``<``
    byte offset) through ``contents_close`` (the ``>`` byte offset, inclusive).

    Per ISO 32000-1 §12.8.1, the digest is taken over the entire file
    *except* the bytes strictly between ``<`` and ``>`` — the angle
    brackets themselves are *included* in the hashed range:

        range1 = [0 .. contents_open]            (includes ``<``)
        range2 = [contents_close .. file_end]    (includes ``>``)

    Raises :class:`ValueError` if the offsets don't sit inside the buffer
    or if ``contents_close`` is not strictly greater than ``contents_open``.
    """
    n = len(document_bytes)
    if not (0 <= contents_open < n and 0 <= contents_close < n):
        raise ValueError(
            f"/Contents placeholder offsets out of range: "
            f"open={contents_open} close={contents_close} file_size={n}"
        )
    if contents_close <= contents_open:
        raise ValueError(
            f"/Contents placeholder is malformed: close ({contents_close}) "
            f"must be strictly greater than open ({contents_open})"
        )
    start1 = 0
    len1 = contents_open + 1  # include `<`
    start2 = contents_close  # include `>`
    len2 = n - start2
    return [start1, len1, start2, len2]


def compute_signed_digest(
    document_bytes: bytes | bytearray,
    byte_range: list[int],
    *,
    algorithm: str = "sha256",
) -> bytes:
    """Recompute the message digest the signature was taken over.

    Concatenates the two slices identified by ``byte_range`` =
    ``[start1, len1, start2, len2]`` and hashes them with ``algorithm``
    (default ``"sha256"`` — matches ``adbe.pkcs7.detached`` which uses
    SHA-256 for new signatures; pass ``"sha1"`` for ``adbe.pkcs7.sha1``).
    """
    if len(byte_range) != 4:
        raise ValueError(
            f"/ByteRange must have exactly 4 entries, got {len(byte_range)}"
        )
    start1, len1, start2, len2 = byte_range
    chunk = bytes(document_bytes[start1 : start1 + len1]) + bytes(
        document_bytes[start2 : start2 + len2]
    )
    return hashlib.new(algorithm, chunk).digest()


# ----------------------------------------------------------- PKCS#7 DER scanner

# OID 1.2.840.113549.1.9.4 (id-pkcs9-at-messageDigest) DER-encoded:
#     06 09 2A 86 48 86 F7 0D 01 09 04
# Tag 0x06 = OBJECT IDENTIFIER, length 0x09, then the body bytes:
#     2A 86 48 86 F7 0D 01 09 04
_MESSAGE_DIGEST_OID_DER: bytes = bytes.fromhex("06092A864886F70D010904")


def _read_der_length(buf: bytes, offset: int) -> tuple[int, int]:
    """Decode a DER length starting at ``offset``. Returns ``(length, n_bytes)``
    where ``n_bytes`` is how many bytes the length encoding occupied
    (1 for short form, 2..N for long form).

    Indefinite-length form (``0x80``) is rejected — DER forbids it.
    Raises :class:`ValueError` on malformed input.
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


def extract_pkcs7_message_digest(pkcs7_der: bytes) -> bytes | None:
    """Locate and return the ``messageDigest`` signed-attribute value from a
    DER-encoded PKCS#7 / CMS SignedData blob.

    Implementation: scans for the ``messageDigest`` OID DER prefix
    (``06 09 2A 86 48 86 F7 0D 01 09 04``), then parses the following
    ``SET OF AttributeValue`` to yield the inner ``OCTET STRING`` payload.
    Returns the digest bytes on success, ``None`` if the OID is absent or
    the surrounding ASN.1 isn't shaped like a CMS signed-attribute (the
    caller treats ``None`` as "couldn't recover digest" — not an error).

    Hand-rolled to avoid an ``asn1crypto`` dep; see ``CHANGES.md``.
    """
    idx = pkcs7_der.find(_MESSAGE_DIGEST_OID_DER)
    if idx < 0:
        return None
    # After the OID DER (11 bytes), the AttributeValues SET begins:
    #     31 LL  (SET tag, length, contents)
    #         04 LL <digest>  (OCTET STRING tag, length, body)
    cursor = idx + len(_MESSAGE_DIGEST_OID_DER)
    if cursor >= len(pkcs7_der):
        return None
    try:
        if pkcs7_der[cursor] != 0x31:  # SET (universal, constructed, tag 17)
            return None
        cursor += 1
        set_len, n = _read_der_length(pkcs7_der, cursor)
        cursor += n
        set_end = cursor + set_len
        if set_end > len(pkcs7_der):
            return None
        if cursor >= set_end or pkcs7_der[cursor] != 0x04:
            return None  # OCTET STRING expected
        cursor += 1
        os_len, n = _read_der_length(pkcs7_der, cursor)
        cursor += n
        if cursor + os_len > set_end:
            return None
        return pkcs7_der[cursor : cursor + os_len]
    except ValueError:
        return None


__all__ = [
    "check_certificate_usage",
    "check_responder_certificate_usage",
    "check_time_stamp_certificate_usage",
    "compute_byte_range",
    "compute_signed_digest",
    "extract_pkcs7_message_digest",
    "get_last_relevant_signature",
    "get_mdp_permission",
    "set_mdp_permission",
]
