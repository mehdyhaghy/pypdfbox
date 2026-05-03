from __future__ import annotations

import datetime as _dt
import hashlib

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString

from .pd_prop_build import PDPropBuild
from .signature_validation_result import SignatureValidationResult

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
        Returns ``None`` if no ``/ByteRange`` is present.
        """
        br = self.get_byte_range()
        if br is None:
            return None
        start1, len1, start2, len2 = br
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

    def verify(self, document_bytes: bytes) -> SignatureValidationResult:
        """Verify this signature against ``document_bytes``.

        Best-effort partial implementation:

        1. Computes the document digest over the ``/ByteRange`` slices.
        2. Extracts the signer certificate from the PKCS#7 ``/Contents``
           blob via :func:`cryptography.hazmat.primitives.serialization.
           pkcs7.load_der_pkcs7_certificates`.
        3. Tries to recover the ``messageDigest`` signed-attribute (OID
           ``1.2.840.113549.1.9.4``) from the SignedData ASN.1 with a
           minimal hand-rolled DER walker (we intentionally avoid an
           ``asn1crypto`` dep — see ``CHANGES.md``).
        4. If both digests are present, compares them and sets
           :attr:`SignatureValidationResult.is_valid` accordingly.

        **NOT implemented** (TODO — chain trust, signature-math
        verification over the signed-attributes, timestamp validation,
        revocation): a digest-match success here means the signed bytes
        were not altered, *not* that the signing certificate is trusted.
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
        if result.signed_digest is not None and result.computed_digest is not None:
            if result.signed_digest == result.computed_digest:
                result.is_valid = True
            else:
                result.errors.append(
                    "digest mismatch: messageDigest signed-attribute does "
                    "not match recomputed /ByteRange digest"
                )
                result.is_valid = False
        else:
            result.errors.append(
                "messageDigest signed-attribute not found in PKCS#7 — "
                "cannot perform digest-match check"
            )
            result.is_valid = False

        # TODO: full chain trust + signature math over signed-attributes
        # (cryptography's high-level pkcs7 API is signing-only). Tracked
        # in CHANGES.md.
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
