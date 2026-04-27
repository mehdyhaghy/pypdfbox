from __future__ import annotations

import hashlib

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString

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

    def __init__(self, dictionary: COSDictionary | None = None) -> None:
        if dictionary is None:
            self._dict = COSDictionary()
            self._dict.set_item(_TYPE, _SIG)
        else:
            self._dict = dictionary

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Filter ----------

    def get_filter(self) -> str | None:
        return self._dict.get_name(_FILTER)

    def set_filter(self, name: str | None) -> None:
        if name is None:
            self._dict.remove_item(_FILTER)
            return
        self._dict.set_name(_FILTER, name)

    # ---------- /SubFilter ----------

    def get_sub_filter(self) -> str | None:
        return self._dict.get_name(_SUB_FILTER)

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

    # ---------- verify ----------

    def verify(self, document_bytes: bytes) -> SignatureValidationResult:
        """Verify this signature against ``document_bytes``.

        Partial implementation: computes the document digest from
        ``/ByteRange`` and extracts the signer certificate from the
        embedded PKCS#7 SignedData blob. Full PKCS#7 SignedData chain
        validation (signed-attributes verification, signature math,
        certificate-chain trust) is **deferred** — see :class:`
        SignatureValidationResult` and ``CHANGES.md``. Always returns a
        result with ``is_valid=False`` until the full path is implemented.
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

            certs = pkcs7.load_der_pkcs7_certificates(contents)
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

        # Full PKCS#7 SignedData verification (signed-attribute hash match,
        # signature-over-signed-attributes, chain trust) is not implemented:
        # cryptography's high-level API is signing-only. A full port needs
        # asn1crypto or manual ASN.1 walking — tracked in CHANGES.md.
        result.errors.append(
            "full PKCS#7 SignedData verification deferred — "
            "only certificate extraction implemented"
        )
        result.is_valid = False
        return result


__all__ = ["PDPropBuild", "PDSignature", "SignatureValidationResult"]
