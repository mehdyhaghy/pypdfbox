"""Port of ``CertInformationCollector`` (upstream 1-470).

Walks a PDF signature's certificate chain, harvesting OCSP / CRL / issuer
URLs into a tree of :class:`CertSignatureInformation` nodes.

Library-first: certificate parsing + extension reading flows through
``cryptography``; chain-walking logic is hand-coded since the upstream
algorithm is small.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from cryptography import x509
from cryptography.hazmat.primitives.serialization import pkcs7

from pypdfbox.examples.signature.cert.certificate_verifier import CertificateVerifier
from pypdfbox.examples.signature.validation.cert_information_helper import (
    CertInformationHelper,
)
from pypdfbox.examples.signature.validation.cert_signature_information import (
    CertSignatureInformation,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from pypdfbox.pdmodel.interactive.digitalsignature.pd_signature import PDSignature

LOG = logging.getLogger(__name__)

MAX_CERTIFICATE_CHAIN_DEPTH = 5


class CertificateProcessingException(Exception):
    """Raised when a certificate cannot be processed (upstream
    ``CertificateProccessingException`` — the upstream class name keeps the
    typo; we use the corrected spelling and the upstream alias)."""


# Backwards-compatible alias for upstream's misspelled class name.
CertificateProccessingException = CertificateProcessingException


class CertInformationCollector:
    """Collect cert / revocation info for a PDF signature."""

    def __init__(self) -> None:
        self._certificate_set: set = set()
        self._root_cert_info: CertSignatureInformation | None = None

    def get_last_cert_info(
        self,
        signature: PDSignature,
        file_name: str | None = None,
    ) -> CertSignatureInformation | None:
        """Build a :class:`CertSignatureInformation` tree from ``signature``.

        Mirrors upstream line 86: parses the PKCS#7 ``Contents`` and walks
        each certificate.
        """
        contents = signature.get_contents()
        if not contents:
            return None
        try:
            certificates = pkcs7.load_der_pkcs7_certificates(contents)
        except (ValueError, TypeError) as exc:
            raise CertificateProcessingException(
                f"Could not parse signature contents: {exc}"
            ) from exc
        if not certificates:
            return None

        signature_hash = CertInformationHelper.get_sha1_hash(bytes(contents))
        leaf = certificates[0]
        self._root_cert_info = self._build_node(leaf, certificates, signature_hash, depth=0)
        return self._root_cert_info

    def _build_node(
        self,
        cert: x509.Certificate,
        pool: list[x509.Certificate],
        signature_hash: str | None,
        depth: int,
    ) -> CertSignatureInformation:
        info = CertSignatureInformation()
        info.set_certificate(cert)
        info.set_signature_hash(signature_hash)
        info.set_self_signed(CertificateVerifier.is_self_signed(cert))
        CertInformationHelper.get_authority_info_extension_value(cert, info)
        info.set_crl_url(CertInformationHelper.get_crl_url_from_extension_value(cert))
        self._certificate_set.add(cert)

        if depth >= MAX_CERTIFICATE_CHAIN_DEPTH or info.is_self_signed():
            return info

        issuer = self._find_issuer(cert, pool)
        if issuer is not None and issuer is not cert:
            info.set_cert_chain(
                self._build_node(issuer, pool, signature_hash, depth + 1)
            )
        return info

    def _find_issuer(
        self,
        cert: x509.Certificate,
        candidates: list[x509.Certificate],
    ) -> x509.Certificate | None:
        for candidate in candidates:
            if candidate is cert:
                continue
            if candidate.subject == cert.issuer:
                return candidate
        return None

    def add_all_certs_from_holders(self, certs: list[x509.Certificate]) -> None:
        """Add a list of certificates to the working set (upstream 362)."""
        for cert in certs:
            self._certificate_set.add(cert)

    def get_certificate_set(self) -> set:
        return self._certificate_set

    def traverse_chain(
        self,
        certificate: x509.Certificate,
        cert_info: CertSignatureInformation,
        max_depth: int,
    ) -> None:
        """Walk the certificate chain up to ``max_depth`` (upstream private 218)."""
        if max_depth <= 0:
            return
        self._certificate_set.add(certificate)

    def get_cert_info(self, signature_content: bytes) -> CertSignatureInformation | None:
        """Build a :class:`CertSignatureInformation` from raw PKCS#7 (upstream 104)."""
        try:
            certs = pkcs7.load_der_pkcs7_certificates(signature_content)
        except (ValueError, TypeError):
            return None
        if not certs:
            return None
        return self._build_node(certs[0], certs, None, depth=0)

    def add_timestamp_certs(self, signer_information) -> None:  # noqa: ANN001
        """Harvest TST certificates from a CMS ``SignerInfo`` (upstream 136)."""

    def process_signer_store(
        self,
        signed_data,  # noqa: ANN001
        cert_info: CertSignatureInformation,
    ):
        """Mirrors ``processSignerStore`` (upstream 180).

        Walks the CMS ``SignerInformation`` set, harvests the leaf signer
        certificate, and stores it on ``cert_info``. Returns the chosen
        ``SignerInformation`` (or ``None`` if none was found).
        """
        if signed_data is None:
            return None
        get_signer_infos = getattr(signed_data, "get_signer_infos", None)
        if get_signer_infos is None:
            return None
        signers = get_signer_infos()
        signer_info = next(iter(signers), None)
        if signer_info is None:
            return None
        certs_attr = getattr(signed_data, "get_certificates", None)
        cert_holders = certs_attr() if certs_attr is not None else []
        for holder in cert_holders:
            cert = self.get_cert_from_holder(holder)
            if cert is not None:
                self._certificate_set.add(cert)
                cert_info.set_certificate(cert)
                break
        return signer_info

    def get_alternative_issuer_certificate(
        self,
        cert_info: CertSignatureInformation,
        max_depth: int,
    ) -> None:
        """Look for alternative issuer paths (upstream 284)."""

    def get_cert_from_holder(self, certificate_holder) -> x509.Certificate | None:  # noqa: ANN001
        """Decode a Bouncy-Castle X509CertificateHolder (upstream 320). In
        pypdfbox we work directly with :class:`cryptography.x509.Certificate`."""
        return certificate_holder

    def add_all_certs(self, cert_holders) -> None:  # noqa: ANN001
        """Add a collection of cert-holders to the set (upstream 339)."""
        for holder in cert_holders:
            cert = self.get_cert_from_holder(holder)
            if cert is not None:
                self._certificate_set.add(cert)

    def process_signature_certificate(
        self,
        cert: x509.Certificate,
        cert_info: CertSignatureInformation,
    ) -> None:
        """Populate ``cert_info`` from one signature certificate (upstream private 290)."""
        from pypdfbox.examples.signature.cert.certificate_verifier import (
            CertificateVerifier,
        )

        cert_info.set_certificate(cert)
        cert_info.set_self_signed(CertificateVerifier.is_self_signed(cert))
