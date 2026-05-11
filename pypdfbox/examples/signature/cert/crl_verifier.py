"""Port of ``CRLVerifier`` (upstream 1-359).

Provides helpers for extracting CRL distribution points from an X.509
certificate, fetching the CRL, and checking whether the certificate has
been revoked.

Library-first: ``cryptography.x509`` does the CRL parsing and extension
walking; we wrap it with the upstream-shaped helper API.
"""

from __future__ import annotations

import datetime as _dt
import logging
from collections.abc import Iterable

from cryptography import x509
from cryptography.x509.oid import ExtensionOID

from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)

LOG = logging.getLogger(__name__)


class CRLVerifier:
    """Static helpers for CRL-based revocation checking."""

    def __init__(self) -> None:  # pragma: no cover - mirrors private ctor
        raise RuntimeError("CRLVerifier is a static helper class")

    @staticmethod
    def verify_certificate_crls(
        cert: x509.Certificate,
        sign_date: _dt.datetime,
        additional_certs: Iterable[x509.Certificate],
        crl_overrides: dict[str, x509.CertificateRevocationList] | None = None,
    ) -> None:
        """Walk CRL distribution points and check ``cert`` against each.

        ``crl_overrides`` lets callers (and tests) inject pre-fetched CRLs
        keyed by URL — keeping the API offline-friendly. Mirrors upstream
        line 91, except the upstream version actually downloads CRLs.
        """
        crl_overrides = crl_overrides or {}
        for url in CRLVerifier.get_crl_distribution_points(cert):
            crl = crl_overrides.get(url)
            if crl is None:
                LOG.warning("No CRL provided for distribution point %s", url)
                continue
            CRLVerifier.check_revocation(crl, cert, sign_date)

    @staticmethod
    def verify_certificate_cr_ls(
        cert: x509.Certificate,
        sign_date: _dt.datetime,
        additional_certs: Iterable[x509.Certificate],
        crl_overrides: dict[str, x509.CertificateRevocationList] | None = None,
    ) -> None:
        """Snake-case spelling matching ``camel_to_snake('verifyCertificateCRLs')``."""
        CRLVerifier.verify_certificate_crls(
            cert, sign_date, additional_certs, crl_overrides,
        )

    @staticmethod
    def check_revocation(
        crl: x509.CertificateRevocationList,
        cert: x509.Certificate,
        sign_date: _dt.datetime,
    ) -> None:
        """Raise :class:`RevokedCertificateException` if ``cert`` appears in ``crl``."""
        entry = crl.get_revoked_certificate_by_serial_number(cert.serial_number)
        if entry is None:
            return
        revocation_date = getattr(entry, "revocation_date_utc", None) or entry.revocation_date
        if sign_date is not None and revocation_date > sign_date:
            # Certificate revoked AFTER the signing date — not relevant
            return
        raise RevokedCertificateException(
            f"Certificate revoked at {revocation_date.isoformat()}",
            revocation_time=revocation_date,
        )

    @staticmethod
    def download_crl(url: str) -> bytes:
        """Stub for HTTP CRL download (upstream private). Offline by default."""
        return b""

    @staticmethod
    def download_crl_from_web(url: str) -> bytes:
        """Stub for HTTPS CRL download (upstream private). Offline by default."""
        return b""

    @staticmethod
    def download_crl_from_ldap(url: str) -> bytes:
        """Stub for LDAP CRL download (upstream 261). Offline by default."""
        return b""

    @staticmethod
    def get_crl_distribution_points(cert: x509.Certificate) -> list[str]:
        """Return the http(s) CRL distribution point URLs from ``cert``."""
        try:
            ext = cert.extensions.get_extension_for_oid(
                ExtensionOID.CRL_DISTRIBUTION_POINTS
            )
        except x509.ExtensionNotFound:
            return []
        urls: list[str] = []
        for point in ext.value:  # type: ignore[attr-defined]
            full_name = getattr(point, "full_name", None)
            if not full_name:
                continue
            for name in full_name:
                if isinstance(name, x509.UniformResourceIdentifier):
                    value = name.value
                    if value.startswith("http"):
                        urls.append(value)
        return urls
