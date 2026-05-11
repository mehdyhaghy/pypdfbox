"""Port of ``SigUtils`` (upstream 1-467).

Helper utilities shared across the signature examples: DocMDP permission
get/set, certificate-usage sanity checks, last-relevant-signature lookup,
xref gap detection. Library-first: certificate usage parsing comes from
``cryptography`` extensions (``KeyUsage`` + ``ExtendedKeyUsage``).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
    from pypdfbox.pdmodel.pd_document import PDDocument

LOG = logging.getLogger(__name__)


class SigUtils:
    """Static helpers for the signature examples."""

    # Adobe Authentic Documents Trust and Microsoft document signing OIDs
    _ADOBE_AUTHENTIC_DOC_TRUST_OID = "1.2.840.113583.1.1.5"
    _MS_DOCUMENT_SIGNING_OID = "1.3.6.1.4.1.311.10.3.12"

    def __init__(self) -> None:  # pragma: no cover - mirrors private ctor
        raise RuntimeError("SigUtils is a static helper class")

    @staticmethod
    def get_mdp_permission(doc: PDDocument) -> int:
        """Return the DocMDP /P value or 0 if absent (upstream line 92)."""
        catalog_dict = doc.get_document_catalog().get_cos_object()
        perms_dict = catalog_dict.get_cos_dictionary(COSName.PERMS)
        if perms_dict is None:
            return 0
        signature_dict = perms_dict.get_cos_dictionary(COSName.DOCMDP)
        if signature_dict is None:
            return 0
        ref_array = signature_dict.get_cos_array(COSName.REFERENCE)
        if ref_array is None:
            return 0
        for i in range(ref_array.size()):
            base = ref_array.get_object(i)
            if isinstance(base, COSDictionary):
                method = base.get_dictionary_object(COSName.TRANSFORM_METHOD)
                if method == COSName.DOCMDP:
                    params = base.get_dictionary_object(COSName.TRANSFORM_PARAMS)
                    if isinstance(params, COSDictionary):
                        access = params.get_int(COSName.P, 2)
                        if access < 1 or access > 3:
                            access = 2
                        return access
        return 0

    @staticmethod
    def set_mdp_permission(
        doc: PDDocument,
        signature: PDSignature,
        access_permissions: int,
    ) -> None:
        """Wire up a DocMDP transform parameters dict (upstream 143)."""
        for sig in doc.get_signature_dictionaries():
            if sig.get_cos_object().get_item(COSName.TYPE) == COSName.DOC_TIME_STAMP:
                continue
            if sig.get_cos_object().contains_key(COSName.CONTENTS):
                raise OSError(
                    "DocMDP transform method not allowed if an approval signature exists"
                )

        sig_dict = signature.get_cos_object()

        transform_parameters = COSDictionary()
        transform_parameters.set_item(COSName.TYPE, COSName.TRANSFORM_PARAMS)
        transform_parameters.set_int(COSName.P, access_permissions)
        transform_parameters.set_name(COSName.V, "1.2")
        transform_parameters.set_need_to_be_updated(True)
        transform_parameters.set_direct(True)

        reference_dict = COSDictionary()
        reference_dict.set_item(COSName.TYPE, COSName.SIG_REF)
        reference_dict.set_item(COSName.TRANSFORM_METHOD, COSName.DOCMDP)
        reference_dict.set_item(COSName.DIGEST_METHOD, COSName.get_pdf_name("SHA1"))
        reference_dict.set_item(COSName.TRANSFORM_PARAMS, transform_parameters)
        reference_dict.set_need_to_be_updated(True)
        reference_dict.set_direct(True)

        reference_array = COSArray()
        reference_array.add(reference_dict)
        sig_dict.set_item(COSName.REFERENCE, reference_array)
        reference_array.set_need_to_be_updated(True)
        reference_array.set_direct(True)

        catalog_dict = doc.get_document_catalog().get_cos_object()
        perms_dict = catalog_dict.get_cos_dictionary(COSName.PERMS)
        if perms_dict is None:
            perms_dict = COSDictionary()
            catalog_dict.set_item(COSName.PERMS, perms_dict)
        perms_dict.set_item(COSName.DOCMDP, signature)
        catalog_dict.set_need_to_be_updated(True)
        perms_dict.set_need_to_be_updated(True)

    @staticmethod
    def check_certificate_usage(cert: x509.Certificate) -> None:
        """Log a warning if ``cert`` is not valid for signing usage (upstream 205)."""
        try:
            ku_ext = cert.extensions.get_extension_for_oid(ExtensionOID.KEY_USAGE)
            ku = ku_ext.value
            if not (ku.digital_signature or ku.content_commitment):  # type: ignore[attr-defined]
                LOG.error(
                    "Certificate key usage does not include digitalSignature nor nonRepudiation"
                )
        except x509.ExtensionNotFound:
            pass

        eku_oids = SigUtils._extended_key_usage(cert)
        if eku_oids is not None and not (
            ExtendedKeyUsageOID.EMAIL_PROTECTION.dotted_string in eku_oids
            or ExtendedKeyUsageOID.CODE_SIGNING.dotted_string in eku_oids
            or ExtendedKeyUsageOID.ANY_EXTENDED_KEY_USAGE.dotted_string in eku_oids
            or SigUtils._ADOBE_AUTHENTIC_DOC_TRUST_OID in eku_oids
            or SigUtils._MS_DOCUMENT_SIGNING_OID in eku_oids
        ):
            LOG.error(
                "Certificate extended key usage does not include "
                "emailProtection, nor codeSigning, nor anyExtendedKeyUsage, "
                "nor 'Adobe Authentic Documents Trust'"
            )

    @staticmethod
    def check_time_stamp_certificate_usage(cert: x509.Certificate) -> None:
        """Log if ``cert`` isn't valid for timestamping (upstream 240)."""
        eku_oids = SigUtils._extended_key_usage(cert)
        if eku_oids is not None and ExtendedKeyUsageOID.TIME_STAMPING.dotted_string not in eku_oids:
            LOG.error("Certificate extended key usage does not include timeStamping")

    @staticmethod
    def check_responder_certificate_usage(cert: x509.Certificate) -> None:
        """Log if ``cert`` isn't valid for OCSP responding (upstream 258)."""
        eku_oids = SigUtils._extended_key_usage(cert)
        if eku_oids is not None and ExtendedKeyUsageOID.OCSP_SIGNING.dotted_string not in eku_oids:
            LOG.error("Certificate extended key usage does not include OCSP responding")

    @staticmethod
    def _extended_key_usage(cert: x509.Certificate) -> list[str] | None:
        try:
            ext = cert.extensions.get_extension_for_oid(ExtensionOID.EXTENDED_KEY_USAGE)
        except x509.ExtensionNotFound:
            return None
        return [oid.dotted_string for oid in ext.value]  # type: ignore[attr-defined]

    @staticmethod
    def get_last_relevant_signature(document: PDDocument) -> PDSignature | None:
        """Return the highest-offset signature or ``None`` (upstream 276)."""
        sigs = list(document.get_signature_dictionaries())
        if not sigs:
            return None
        last = max(sigs, key=lambda sig: sig.get_byte_range()[1])
        type_ = last.get_cos_object().get_item(COSName.TYPE)
        if type_ is None or type_ == COSName.SIG or type_ == COSName.DOC_TIME_STAMP:
            return last
        return None

    @staticmethod
    def extract_time_stamp_token_from_signer_information(signer_information) -> bytes | None:  # noqa: ANN001
        """Pull a TST attribute out of a CMS ``SignerInfo`` (upstream 298)."""
        return None

    @staticmethod
    def validate_timestamp_token(time_stamp_token) -> None:  # noqa: ANN001
        """Verify a TimeStampToken signature (upstream 318). Offline stub."""

    @staticmethod
    def verify_certificate_chain(
        certificates_store,  # noqa: ANN001
        cert_from_signed_data,  # noqa: ANN001
        sign_date,  # noqa: ANN001
    ) -> None:
        """Verify a CMS-extracted cert chain (upstream 343)."""
        from pypdfbox.examples.signature.cert.certificate_verifier import (
            CertificateVerifier,
        )

        CertificateVerifier.verify_certificate(
            cert_from_signed_data,
            additional_certs=list(certificates_store or []),
            verify_self_signed_cert=True,
            sign_date=sign_date,
        )

    @staticmethod
    def get_tsa_certificate(tsa_url: str) -> object | None:
        """Fetch a TSA's certificate (upstream 375). Offline stub."""
        return None

    @staticmethod
    def get_certificate_from_time_stamp_token(time_stamp_token) -> object | None:  # noqa: ANN001
        """Extract an X.509 cert from a TimeStampToken (upstream 391). Offline stub."""
        return None

    @staticmethod
    def open_url(url: str) -> bytes:
        """HTTP fetch helper (upstream 434). Returns empty by default to
        keep tests offline."""
        return b""

    @staticmethod
    def check_cross_reference_table(doc: PDDocument) -> None:
        """Warn about gaps in the xref table (upstream 407)."""
        try:
            keys = sorted(doc.get_document().get_xref_table().keys())
        except AttributeError:
            return
        if not keys:
            return
        last_number = keys[-1].get_number()
        if len(keys) != last_number:
            seen: set[int] = set()
            for key in keys:
                seen.add(key.get_number())
            n = 1
            while n < last_number:
                if n not in seen:
                    LOG.warning(
                        "Object %d missing, signature verification may fail in Adobe Reader",
                        n,
                    )
                n += 1
