"""Port of ``CertInformationHelper`` (upstream 1-166).

Static helpers for hashing PKCS#7 signature blobs and reading the AIA /
CRL distribution-point extension bytes.

Library-first: we don't reimplement ASN.1 — we lean on
:mod:`cryptography.x509` to extract AIA / CRL data directly from the
certificate object, then back-fill the ``CertSignatureInformation`` bag.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.x509.oid import (
    AuthorityInformationAccessOID,
    ExtensionOID,
)

if TYPE_CHECKING:  # pragma: no cover
    from pypdfbox.examples.signature.validation.cert_signature_information import (
        CertSignatureInformation,
    )

LOG = logging.getLogger(__name__)


class CertInformationHelper:
    """Static helpers used by :class:`CertInformationCollector`."""

    def __init__(self) -> None:  # pragma: no cover - private ctor
        raise RuntimeError("CertInformationHelper is a static helper class")

    @staticmethod
    def get_sha1_hash(content: bytes) -> str | None:
        """Return uppercase hex SHA-1 digest of ``content`` (upstream 51)."""
        try:
            digest = hashlib.sha1(content, usedforsecurity=False).digest()
            return digest.hex().upper()
        except Exception:  # noqa: BLE001 - mirror upstream lenient catch
            LOG.error("No SHA-1 Algorithm found", exc_info=True)
            return None

    @staticmethod
    def get_authority_info_extension_value(
        cert: x509.Certificate,
        cert_info: CertSignatureInformation,
    ) -> None:
        """Populate OCSP / caIssuers URLs into ``cert_info`` (upstream 73)."""
        try:
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.AUTHORITY_INFORMATION_ACCESS
            )
        except x509.ExtensionNotFound:
            return
        for descr in ext.value:  # type: ignore[attr-defined]
            if descr.access_method == AuthorityInformationAccessOID.OCSP and isinstance(
                descr.access_location, x509.UniformResourceIdentifier
            ):
                cert_info.set_ocsp_url(descr.access_location.value)
            elif descr.access_method == AuthorityInformationAccessOID.CA_ISSUERS and isinstance(
                descr.access_location, x509.UniformResourceIdentifier
            ):
                cert_info.set_issuer_url(descr.access_location.value)

    @staticmethod
    def extract_crl_url_from_sequence(sequence) -> str | None:  # noqa: ANN001
        """Pull the first http(s) URL from a CRL DP sequence (upstream private 128)."""
        return None

    @staticmethod
    def get_crl_url_from_extension_value(cert: x509.Certificate) -> str | None:
        """Return the first http(s) CRL distribution point URL (upstream 108)."""
        try:
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.CRL_DISTRIBUTION_POINTS
            )
        except x509.ExtensionNotFound:
            return None
        for point in ext.value:  # type: ignore[attr-defined]
            full_name = getattr(point, "full_name", None) or []
            for name in full_name:
                if isinstance(name, x509.UniformResourceIdentifier) and name.value.startswith(
                    "http"
                ):
                    return name.value
        return None
