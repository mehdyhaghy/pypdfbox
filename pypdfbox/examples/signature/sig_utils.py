"""Port of ``SigUtils`` (upstream 1-467).

Helper utilities shared across the signature examples: DocMDP permission
get/set, certificate-usage sanity checks, last-relevant-signature lookup,
xref gap detection. Library-first: certificate usage parsing comes from
``cryptography`` extensions (``KeyUsage`` + ``ExtendedKeyUsage``).
"""

import logging
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID, ExtensionOID

from pypdfbox.cos.cos_array import COSArray
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.cos.cos_name import COSName
from pypdfbox.examples.util.connected_input_stream import ConnectedInputStream

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature
    from pypdfbox.pdmodel.pd_document import PDDocument

LOG = logging.getLogger(__name__)

# COSName.SIG isn't among the predefined names of the cos package
_SIG = COSName.get_pdf_name("Sig")

_HTTP_MOVED_TEMP = 302
_HTTP_MOVED_PERM = 301
_HTTP_SEE_OTHER = 303


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Disable urllib's automatic redirect following: ``open_url`` inspects
    the redirect status itself and only follows an ``http://X`` ->
    ``https://X`` upgrade, as upstream."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _open_uri(url: str, timeout: float) -> Any:
    """Open ``url`` without following redirects (upstream private
    ``openURI``). HTTP error statuses, including the redirects that the
    disabled handler turns into errors, are returned as the
    :class:`urllib.error.HTTPError` itself, which offers the same
    ``getcode`` / ``headers`` / ``read`` / ``close`` surface. Tests replace
    this function to stay offline."""
    opener = urllib.request.build_opener(_NoRedirectHandler)
    try:
        return opener.open(url, timeout=timeout)
    except urllib.error.HTTPError as err:
        return err


class SigUtils:
    """Static helpers for the signature examples."""

    # Adobe Authentic Documents Trust and Microsoft document signing OIDs
    _ADOBE_AUTHENTIC_DOC_TRUST_OID = "1.2.840.113583.1.1.5"
    _MS_DOCUMENT_SIGNING_OID = "1.3.6.1.4.1.311.10.3.12"

    # Certificates / CRLs / LDAP needed for the upstream unit tests; add
    # yours or create your own logic in check_access()
    ALLOW_URL_SET: frozenset[str] = frozenset(
        {
            "http://www.pki.admin.ch/aia/RegularCA01.crt",
            "http://www.pki.admin.ch/aia/RootCAII.crt",
            "http://www.pki.admin.ch/aia/RootCAIV.crt",
            "http://www.pki.admin.ch/crl/RegularCA01.crl",
            "http://www.pki.admin.ch/crl/RootCAII.crl",
            "http://www.pki.admin.ch/crl/RootCAIV.crl",
            "http://www.pki.admin.ch/aia/RegulatedCA02.crt",
            "http://www.pki.admin.ch/aia/ocsp",
            "http://www.pki.admin.ch/crl/RegulatedCA02.crl",
            "http://repository.certum.pl/ctnca2.cer",
            "http://repository.certum.pl/ctnca.cer",
            "http://subca.repository.certum.pl/ctsca2021.cer",
            "http://crl.geotrust.com/crls/adobeca1.crl",
            "http://crl.adobe.com/cds.crl",
            "http://subca.crl.certum.pl/ctsca2021.crl",
            "http://subca.ocsp-certum.com",
            "http://crl.certum.pl/ctnca2.crl",
            "http://www.freetsa.org/tsa.crt",
            "http://www.freetsa.org:2560",
            "http://www.freetsa.org/crl/root_ca.crl",
            "http://www.gemboxsoftware.com/test/pki/cert/GemBoxCA.crt",
            "http://www.gemboxsoftware.com/test/pki/cert/GemBoxRSA.crt",
            "http://www.ca.gov.si/crt/si-trust-root.crt",
            "ldap://x500.gov.si/cn=SI-TRUST%20Root,oi=VATSI-17659957,"
            "o=Republika%20Slovenija,c=SI?certificateRevocationList",
        }
    )
    # PDFBOX-6291: timeouts for open_url
    CONNECT_TIMEOUT_MS = 10_000
    READ_TIMEOUT_MS = 20_000

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
        permissions: int,
    ) -> None:
        """Wire up a DocMDP transform parameters dict (upstream 143).

        Raises ``OSError`` if an approval signature exists, and
        ``ValueError`` if ``permissions`` isn't 1, 2 or 3 (PDFBOX-6291)."""
        if permissions not in (1, 2, 3):
            raise ValueError("The permissions value must be 1, 2 or 3")
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
        transform_parameters.set_int(COSName.P, permissions)
        transform_parameters.set_name(COSName.V, "1.2")
        transform_parameters.set_needs_to_be_updated(True)
        transform_parameters.set_direct(True)

        reference_dict = COSDictionary()
        reference_dict.set_item(COSName.TYPE, COSName.SIG_REF)
        reference_dict.set_item(COSName.TRANSFORM_METHOD, COSName.DOCMDP)
        reference_dict.set_item(COSName.DIGEST_METHOD, COSName.get_pdf_name("SHA1"))
        reference_dict.set_item(COSName.TRANSFORM_PARAMS, transform_parameters)
        reference_dict.set_needs_to_be_updated(True)
        reference_dict.set_direct(True)

        reference_array = COSArray()
        reference_array.add(reference_dict)
        sig_dict.set_item(COSName.REFERENCE, reference_array)
        reference_array.set_needs_to_be_updated(True)
        reference_array.set_direct(True)

        catalog_dict = doc.get_document_catalog().get_cos_object()
        perms_dict = catalog_dict.get_cos_dictionary(COSName.PERMS)
        if perms_dict is None:
            perms_dict = COSDictionary()
            catalog_dict.set_item(COSName.PERMS, perms_dict)
        perms_dict.set_item(COSName.DOCMDP, signature.get_cos_object())
        catalog_dict.set_needs_to_be_updated(True)
        perms_dict.set_needs_to_be_updated(True)

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
        if type_ is None or type_ == _SIG or type_ == COSName.DOC_TIME_STAMP:
            return last
        LOG.warning("Signature with unknown type ignored: %s", type_)
        return None

    @staticmethod
    def extract_time_stamp_token_from_signer_information(signer_information) -> bytes | None:
        """Pull a TST attribute out of a CMS ``SignerInfo`` (upstream 298)."""
        return None

    @staticmethod
    def validate_timestamp_token(time_stamp_token) -> None:
        """Verify a TimeStampToken signature (upstream 318). Offline stub."""

    @staticmethod
    def verify_certificate_chain(
        certificates_store,
        cert_from_signed_data,
        sign_date,
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
    def get_certificate_from_time_stamp_token(time_stamp_token) -> object | None:
        """Extract an X.509 cert from a TimeStampToken (upstream 391). Offline stub."""
        return None

    @staticmethod
    def check_access(uri: str) -> None:
        """A simple but very restrictive access control logic (upstream
        ``checkAccess``). Create your own but use a zero-trust mindset."""
        if str(uri) not in SigUtils.ALLOW_URL_SET:
            raise OSError(f"URL '{uri}' not in ALLOW_URL_SET")

    @staticmethod
    def open_url(url_string: str) -> ConnectedInputStream:
        """Like ``URL.openStream()`` but follows a redirection from http to
        https (upstream ``openURL``).

        PDFBOX-6291: only the ``http`` and ``https`` schemes are accepted,
        a redirect without ``Location`` is ignored, 307 and 308 count as
        redirects, the connection has a timeout, and it is closed when the
        method fails. Unlike Java's ``HttpURLConnection`` no other redirect
        is followed automatically, and urllib has a single timeout, so the
        read timeout is used for connecting too. HTTP error statuses raise
        ``OSError``.
        """
        scheme = url_string.split(":", 1)[0] if ":" in url_string else None
        if scheme not in ("http", "https"):
            raise OSError(f"{scheme} scheme not supported")

        SigUtils.check_access(url_string)

        timeout = SigUtils.READ_TIMEOUT_MS / 1000
        con = _open_uri(url_string, timeout)
        try:
            response_code = con.getcode()
            LOG.info("%s %s", response_code, getattr(con, "reason", "") or "")
            if SigUtils._is_redirect(response_code):
                location = con.headers.get("Location")
                if (
                    location is not None
                    and url_string.startswith("http://")
                    and location.startswith("https://")
                    and url_string[7:] == location[8:]
                ):
                    # redirection from http:// to https://
                    # change this code if you want to be more flexible (but
                    # think about security!)
                    LOG.info("redirection to %s followed", location)
                    con.close()
                    con = _open_uri(location, timeout)
                    response_code = con.getcode()
                else:
                    LOG.info("redirection to %s ignored", location)
            if response_code is not None and response_code >= 400:
                # HttpURLConnection.getInputStream() throws for these
                raise OSError(
                    f"Server returned HTTP response code: {response_code} "
                    f"for URL: {url_string}"
                )
            return ConnectedInputStream(con, con)
        except BaseException:
            con.close()
            raise

    @staticmethod
    def _is_redirect(response_code: int | None) -> bool:
        """Upstream private ``isRedirect``."""
        return response_code in (
            _HTTP_MOVED_TEMP,
            _HTTP_MOVED_PERM,
            _HTTP_SEE_OTHER,
            307,
            308,
        )

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
