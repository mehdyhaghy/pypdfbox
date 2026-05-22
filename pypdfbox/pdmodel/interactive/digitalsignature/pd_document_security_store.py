"""Typed wrappers for the PDF/A LTV Document Security Store (DSS) and
its per-signature Validation Related Information (VRI) entries.

PDF 32000-2 §12.8.4 (Document Security Store) defines an optional
``/DSS`` entry on the document catalog that bundles long-term
validation evidence — DER-encoded certificates, certificate revocation
lists (CRLs), and OCSP responses — so a signature can be verified after
the issuing CA's certificate expires. Per-signature evidence is keyed
on the hexadecimal form of each signature's ``/Contents`` octet string
inside the optional ``/VRI`` (Validation Related Information) sub-tree.

This module supplies two thin typed wrappers around the COS layer:

* :class:`PDDocumentSecurityStore` — the catalog's ``/DSS`` dictionary.
* :class:`PDValidationInformation` — a single ``/VRI`` value (the
  evidence for one signature).

Both wrappers stay COS-faithful: every accessor materialises through
the underlying :class:`COSDictionary` so direct edits to the COS layer
stay visible. The static helpers ``from_document`` / ``ensure_on`` mirror
the upstream PDFBox idiom (``PDDocumentSecurityStore.fromDocument``).

Library-first: DER blob construction is the caller's responsibility —
this module handles only the PDF-side bundling. A small companion in
``pypdfbox.examples.signature.cert.revocation_collector`` walks a cert
chain and synthesises ``(certs, crls, ocsps)`` tuples ready to plug in.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream, COSString

if TYPE_CHECKING:  # pragma: no cover — typing only
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .pd_signature import PDSignature

LOG = logging.getLogger(__name__)

# /DSS field names (PDF 32000-2 §12.8.4 Table 261).
_DSS = COSName.get_pdf_name("DSS")
_TYPE = COSName.get_pdf_name("Type")
_CERTS = COSName.get_pdf_name("Certs")
_CRLS = COSName.get_pdf_name("CRLs")
_OCSPS = COSName.get_pdf_name("OCSPs")
_VRI = COSName.get_pdf_name("VRI")
_CERT = COSName.get_pdf_name("Cert")
_CRL = COSName.get_pdf_name("CRL")
_OCSP = COSName.get_pdf_name("OCSP")
_TS = COSName.get_pdf_name("TS")
_TU = COSName.get_pdf_name("TU")


def _ensure_cos_stream(blob: bytes | bytearray | memoryview | COSStream) -> COSStream:
    """Return ``blob`` as a ``COSStream`` — wrapping raw bytes when needed.

    The wrapped form carries the DER payload verbatim (no filter chain);
    PDF 32000-2 leaves the filter choice to the producer, and unfiltered
    storage keeps the evidence inspectable by validators that don't ship
    a /FlateDecode implementation.
    """
    if isinstance(blob, COSStream):
        return blob
    if not isinstance(blob, (bytes, bytearray, memoryview)):
        raise TypeError(
            "DSS entry: expected bytes / bytearray / memoryview / COSStream, "
            f"got {type(blob).__name__}"
        )
    stream = COSStream()
    stream.set_data(bytes(blob))
    stream.set_needs_to_be_updated(True)
    return stream


def _streams_to_array(
    blobs: Iterable[bytes | bytearray | memoryview | COSStream],
) -> COSArray:
    arr = COSArray()
    for blob in blobs:
        arr.add(_ensure_cos_stream(blob))
    return arr


def _array_to_byte_blobs(arr: COSArray | None) -> list[bytes]:
    """Resolve an array of stream references back to raw bytes."""
    out: list[bytes] = []
    if arr is None:
        return out
    for entry in arr:
        resolved = entry.get_object() if hasattr(entry, "get_object") else entry
        if isinstance(resolved, COSStream):
            out.append(resolved.to_byte_array())
    return out


class PDValidationInformation:
    """Typed wrapper for one ``/VRI`` value (PDF 32000-2 §12.8.4.2 Table 262).

    A ``/VRI`` entry carries the *minimum* validation evidence needed
    for a single signature: any combination of ``/Cert`` (certs in the
    chain), ``/CRL`` (revocation lists that cover them), ``/OCSP`` (OCSP
    responses that cover them), optional ``/TS`` (a DER-encoded RFC 3161
    timestamp token) and optional ``/TU`` (the time the validation was
    performed). Every entry except ``/TU`` is an indirect-reference
    array of streams; ``/TU`` is a PDF date string.
    """

    def __init__(self, cos_dict: COSDictionary | None = None) -> None:
        self._dict = cos_dict if cos_dict is not None else COSDictionary()

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Cert ----------

    def get_certs(self) -> list[bytes]:
        return _array_to_byte_blobs(self._dict.get_cos_array(_CERT))

    def set_certs(
        self, certs: Iterable[bytes | bytearray | memoryview | COSStream] | None
    ) -> None:
        if certs is None:
            self._dict.remove_item(_CERT)
            return
        self._dict.set_item(_CERT, _streams_to_array(certs))

    # ---------- /CRL ----------

    def get_crls(self) -> list[bytes]:
        return _array_to_byte_blobs(self._dict.get_cos_array(_CRL))

    def set_crls(
        self, crls: Iterable[bytes | bytearray | memoryview | COSStream] | None
    ) -> None:
        if crls is None:
            self._dict.remove_item(_CRL)
            return
        self._dict.set_item(_CRL, _streams_to_array(crls))

    # ---------- /OCSP ----------

    def get_ocsps(self) -> list[bytes]:
        return _array_to_byte_blobs(self._dict.get_cos_array(_OCSP))

    def set_ocsps(
        self, ocsps: Iterable[bytes | bytearray | memoryview | COSStream] | None
    ) -> None:
        if ocsps is None:
            self._dict.remove_item(_OCSP)
            return
        self._dict.set_item(_OCSP, _streams_to_array(ocsps))

    # ---------- /TS (timestamp token bytes) ----------

    def get_timestamp(self) -> bytes | None:
        v = self._dict.get_dictionary_object(_TS)
        if isinstance(v, COSStream):
            return v.to_byte_array()
        if isinstance(v, COSString):
            return v.get_bytes()
        return None

    def set_timestamp(self, token: bytes | bytearray | memoryview | None) -> None:
        if token is None:
            self._dict.remove_item(_TS)
            return
        self._dict.set_item(_TS, _ensure_cos_stream(token))

    # ---------- /TU (PDF date string of the validation moment) ----------

    def get_validation_time(self) -> str | None:
        return self._dict.get_string(_TU)

    def set_validation_time(self, pdf_date: str | None) -> None:
        if pdf_date is None:
            self._dict.remove_item(_TU)
            return
        self._dict.set_string(_TU, pdf_date)


class PDDocumentSecurityStore:
    """Typed wrapper for the catalog's ``/DSS`` dictionary.

    Carries four sub-entries (all optional but at least one is required
    to be meaningful):

    * ``/Certs`` — array of certificate streams (DER-encoded X.509).
    * ``/CRLs`` — array of CRL streams (DER-encoded).
    * ``/OCSPs`` — array of OCSP response streams (DER-encoded).
    * ``/VRI`` — dictionary mapping the uppercase hex form of each
      signature's ``/Contents`` octet string to a
      :class:`PDValidationInformation` value.

    The construction helpers :py:meth:`from_document` / :py:meth:`ensure_on`
    materialise the catalog entry on demand and stamp it dirty so the
    next :meth:`PDDocument.save_incremental` emits it.
    """

    def __init__(self, cos_dict: COSDictionary | None = None) -> None:
        if cos_dict is None:
            cos_dict = COSDictionary()
        self._dict = cos_dict
        # /Type is optional on /DSS but recommended; stamp when fresh.
        if self._dict.get_dictionary_object(_TYPE) is None:
            self._dict.set_item(_TYPE, COSName.get_pdf_name("DSS"))

    def get_cos_object(self) -> COSDictionary:
        return self._dict

    # ---------- /Certs / /CRLs / /OCSPs (document-wide pools) ----------

    def get_certs(self) -> list[bytes]:
        return _array_to_byte_blobs(self._dict.get_cos_array(_CERTS))

    def set_certs(
        self, certs: Iterable[bytes | bytearray | memoryview | COSStream] | None
    ) -> None:
        if certs is None:
            self._dict.remove_item(_CERTS)
            return
        self._dict.set_item(_CERTS, _streams_to_array(certs))

    def add_certs(
        self, certs: Iterable[bytes | bytearray | memoryview | COSStream]
    ) -> None:
        """Append to ``/Certs`` (creating it when absent)."""
        arr = self._dict.get_cos_array(_CERTS)
        if arr is None:
            arr = COSArray()
            self._dict.set_item(_CERTS, arr)
        for blob in certs:
            arr.add(_ensure_cos_stream(blob))

    def get_crls(self) -> list[bytes]:
        return _array_to_byte_blobs(self._dict.get_cos_array(_CRLS))

    def set_crls(
        self, crls: Iterable[bytes | bytearray | memoryview | COSStream] | None
    ) -> None:
        if crls is None:
            self._dict.remove_item(_CRLS)
            return
        self._dict.set_item(_CRLS, _streams_to_array(crls))

    def add_crls(
        self, crls: Iterable[bytes | bytearray | memoryview | COSStream]
    ) -> None:
        arr = self._dict.get_cos_array(_CRLS)
        if arr is None:
            arr = COSArray()
            self._dict.set_item(_CRLS, arr)
        for blob in crls:
            arr.add(_ensure_cos_stream(blob))

    def get_ocsps(self) -> list[bytes]:
        return _array_to_byte_blobs(self._dict.get_cos_array(_OCSPS))

    def set_ocsps(
        self, ocsps: Iterable[bytes | bytearray | memoryview | COSStream] | None
    ) -> None:
        if ocsps is None:
            self._dict.remove_item(_OCSPS)
            return
        self._dict.set_item(_OCSPS, _streams_to_array(ocsps))

    def add_ocsps(
        self, ocsps: Iterable[bytes | bytearray | memoryview | COSStream]
    ) -> None:
        arr = self._dict.get_cos_array(_OCSPS)
        if arr is None:
            arr = COSArray()
            self._dict.set_item(_OCSPS, arr)
        for blob in ocsps:
            arr.add(_ensure_cos_stream(blob))

    # ---------- /VRI ----------

    def get_vri_dictionary(self) -> COSDictionary | None:
        """Return the raw ``/VRI`` dictionary, or ``None`` when absent."""
        return self._dict.get_cos_dictionary(_VRI)

    def ensure_vri_dictionary(self) -> COSDictionary:
        """Return the ``/VRI`` dictionary, creating one when absent."""
        vri = self._dict.get_cos_dictionary(_VRI)
        if vri is None:
            vri = COSDictionary()
            self._dict.set_item(_VRI, vri)
        return vri

    def get_validation_information(
        self, signature_or_key: PDSignature | str | bytes
    ) -> PDValidationInformation | None:
        """Look up the ``/VRI`` entry for ``signature_or_key``.

        ``signature_or_key`` may be a :class:`PDSignature` (the helper
        computes the upstream-prescribed key — uppercase SHA-1 hex of the
        signature's ``/Contents`` octet string), or a pre-computed key
        string, or the raw key bytes.
        """
        vri = self._dict.get_cos_dictionary(_VRI)
        if vri is None:
            return None
        key = self._vri_key_for(signature_or_key)
        entry = vri.get_cos_dictionary(COSName.get_pdf_name(key))
        if entry is None:
            return None
        return PDValidationInformation(entry)

    def set_validation_information(
        self,
        signature_or_key: PDSignature | str | bytes,
        validation_info: PDValidationInformation,
    ) -> None:
        """Install ``validation_info`` under the VRI key for ``signature_or_key``."""
        vri = self.ensure_vri_dictionary()
        key = self._vri_key_for(signature_or_key)
        vri.set_item(COSName.get_pdf_name(key), validation_info.get_cos_object())
        validation_info.get_cos_object().set_needs_to_be_updated(True)
        vri.set_needs_to_be_updated(True)
        self._dict.set_needs_to_be_updated(True)

    # ---------- VRI keying ----------

    @staticmethod
    def _vri_key_for(signature_or_key: PDSignature | str | bytes) -> str:
        """Compute the upstream-prescribed VRI key for a signature.

        PDF 32000-2 §12.8.4.2 / PAdES-LTV (ETSI EN 319 142-1 §B.4)
        require the key to be the uppercase hex of the SHA-1 digest of
        the signature's ``/Contents`` byte string. PDFBox uses that
        convention verbatim.
        """
        if isinstance(signature_or_key, str):
            return signature_or_key.upper()
        if isinstance(signature_or_key, (bytes, bytearray, memoryview)):
            digest = hashlib.sha1(bytes(signature_or_key))  # noqa: S324
            return digest.hexdigest().upper()
        # Import lazily — pd_signature pulls in COS / typing surfaces we
        # already loaded above but the runtime cycle is avoided here.
        from .pd_signature import PDSignature

        if isinstance(signature_or_key, PDSignature):
            contents = signature_or_key.get_contents()
            if contents is None:
                raise ValueError(
                    "VRI key: signature has no /Contents — sign the document "
                    "first or pass an explicit key"
                )
            digest = hashlib.sha1(bytes(contents))  # noqa: S324
            return digest.hexdigest().upper()
        raise TypeError(
            "VRI key: expected PDSignature / str / bytes, got "
            f"{type(signature_or_key).__name__}"
        )

    # ---------- construction helpers ----------

    @staticmethod
    def from_document(document: PDDocument) -> PDDocumentSecurityStore | None:
        """Return the existing ``/DSS`` wrapper for ``document``, or ``None``."""
        catalog = document.get_document_catalog().get_cos_object()
        dss_dict = catalog.get_cos_dictionary(_DSS)
        if dss_dict is None:
            return None
        return PDDocumentSecurityStore(dss_dict)

    @staticmethod
    def ensure_on(document: PDDocument) -> PDDocumentSecurityStore:
        """Return the ``/DSS`` wrapper for ``document``, creating it when absent.

        Stamps both the catalog and the new ``/DSS`` dict as dirty so the
        next :meth:`PDDocument.save_incremental` emits them.
        """
        catalog = document.get_document_catalog().get_cos_object()
        dss_dict = catalog.get_cos_dictionary(_DSS)
        if dss_dict is None:
            dss = PDDocumentSecurityStore()
            catalog.set_item(_DSS, dss.get_cos_object())
            catalog.set_needs_to_be_updated(True)
            dss.get_cos_object().set_needs_to_be_updated(True)
            return dss
        return PDDocumentSecurityStore(dss_dict)

    # ---------- one-shot bundling ----------

    def bundle(
        self,
        *,
        certs: Iterable[bytes | bytearray | memoryview | COSStream] | None = None,
        crls: Iterable[bytes | bytearray | memoryview | COSStream] | None = None,
        ocsps: Iterable[bytes | bytearray | memoryview | COSStream] | None = None,
        signature: PDSignature | None = None,
    ) -> PDValidationInformation | None:
        """Append ``certs`` / ``crls`` / ``ocsps`` to the document-wide pools
        and (when ``signature`` is provided) keep the same evidence in a
        per-signature ``/VRI`` entry.

        Returns the per-signature :class:`PDValidationInformation` when
        a signature was supplied, otherwise ``None``. The returned
        wrapper carries snapshot copies of the supplied blobs (separate
        ``COSStream`` instances) so subsequent edits to the document-wide
        pools don't mutate the per-signature evidence.
        """
        cert_list = list(certs) if certs is not None else []
        crl_list = list(crls) if crls is not None else []
        ocsp_list = list(ocsps) if ocsps is not None else []
        if cert_list:
            self.add_certs(cert_list)
        if crl_list:
            self.add_crls(crl_list)
        if ocsp_list:
            self.add_ocsps(ocsp_list)
        if signature is None:
            return None
        vri_entry = PDValidationInformation()
        if cert_list:
            vri_entry.set_certs(cert_list)
        if crl_list:
            vri_entry.set_crls(crl_list)
        if ocsp_list:
            vri_entry.set_ocsps(ocsp_list)
        self.set_validation_information(signature, vri_entry)
        return vri_entry
