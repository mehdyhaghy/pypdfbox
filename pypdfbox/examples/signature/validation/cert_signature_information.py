"""Port of the nested ``CertInformationCollector.CertSignatureInformation``
data class (upstream lines 402-468). Lifted to its own module to mirror the
parity tracker, which lists it as a sibling class of
``CertInformationCollector``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from cryptography import x509


class CertSignatureInformation:
    """Per-certificate signature / revocation collection bag."""

    def __init__(self) -> None:
        self._certificate: x509.Certificate | None = None
        self._signature_hash: str | None = None
        self._is_self_signed: bool = False
        self._ocsp_url: str | None = None
        self._crl_url: str | None = None
        self._issuer_url: str | None = None
        self._issuer_certificates: set = set()
        self._cert_chain: CertSignatureInformation | None = None
        self._tsa_certs: CertSignatureInformation | None = None
        self._alternative_cert_chain: CertSignatureInformation | None = None

    # ----- setters -----------------------------------------------------
    def set_certificate(self, certificate) -> None:  # noqa: ANN001
        self._certificate = certificate

    def set_signature_hash(self, value: str | None) -> None:
        self._signature_hash = value

    def set_self_signed(self, value: bool) -> None:
        self._is_self_signed = value

    def set_ocsp_url(self, value: str | None) -> None:
        self._ocsp_url = value

    def set_crl_url(self, value: str | None) -> None:
        self._crl_url = value

    def set_issuer_url(self, value: str | None) -> None:
        self._issuer_url = value

    def set_cert_chain(self, value: CertSignatureInformation | None) -> None:
        self._cert_chain = value

    def set_tsa_certs(self, value: CertSignatureInformation | None) -> None:
        self._tsa_certs = value

    def set_alternative_cert_chain(
        self, value: CertSignatureInformation | None
    ) -> None:
        self._alternative_cert_chain = value

    # ----- getters -----------------------------------------------------
    def get_certificate(self):  # noqa: ANN201
        return self._certificate

    def get_signature_hash(self) -> str | None:
        return self._signature_hash

    def is_self_signed(self) -> bool:
        return self._is_self_signed

    def get_ocsp_url(self) -> str | None:
        return self._ocsp_url

    def get_crl_url(self) -> str | None:
        return self._crl_url

    def get_issuer_url(self) -> str | None:
        return self._issuer_url

    def get_issuer_certificates(self) -> set:
        return self._issuer_certificates

    def get_cert_chain(self) -> CertSignatureInformation | None:
        return self._cert_chain

    def get_tsa_certs(self) -> CertSignatureInformation | None:
        return self._tsa_certs

    def get_alternative_cert_chain(self) -> CertSignatureInformation | None:
        return self._alternative_cert_chain
