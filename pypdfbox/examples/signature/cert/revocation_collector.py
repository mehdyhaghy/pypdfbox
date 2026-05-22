"""Helpers for assembling PDF/A LTV (DSS) revocation-info bundles.

Walks a candidate signing-cert chain and packages the DER blobs an
LTV-aware verifier expects under
:class:`pypdfbox.pdmodel.interactive.digitalsignature.PDDocumentSecurityStore`:

* Every certificate in the chain (leaf + intermediates + root) is
  emitted as a DER stream blob in ``certs``.
* Caller-supplied CRLs are emitted DER-encoded in ``crls``.
* Caller-supplied OCSP responses are emitted DER-encoded in ``ocsps``.

The actual *fetching* of CRLs and OCSP responses is intentionally NOT
done here. PDFBox's upstream
``AddValidationInformation.fetchDataUrl`` makes HTTP calls; pypdfbox
stays offline by default (callers plug in their own fetcher and pass
the resulting blobs in). This mirrors the ``crl_overrides`` parameter
that :class:`CRLVerifier.verify_certificate_crls` already exposes.

A small ``build_synthetic_ocsp_response`` helper is provided for tests
and for callers building a self-issued OCSP responder for closed
ecosystems (corporate CA, internal LTV harness, etc.); it wraps the
``cryptography`` library's :class:`OCSPResponseBuilder`.
"""

from __future__ import annotations

import datetime as _dt
import logging
from collections.abc import Iterable
from dataclasses import dataclass

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.types import (
    CertificateIssuerPrivateKeyTypes,
)
from cryptography.hazmat.primitives.serialization import Encoding
from cryptography.x509 import ocsp

LOG = logging.getLogger(__name__)


@dataclass(frozen=True)
class RevocationInfoBundle:
    """The three DER blob lists ready for
    :meth:`PDDocumentSecurityStore.bundle`."""

    certs: list[bytes]
    crls: list[bytes]
    ocsps: list[bytes]

    def is_empty(self) -> bool:
        return not (self.certs or self.crls or self.ocsps)


def collect_revocation_info(
    signer_cert: x509.Certificate,
    intermediate_certs: Iterable[x509.Certificate] = (),
    issuer_cert: x509.Certificate | None = None,
    *,
    crls: Iterable[x509.CertificateRevocationList] = (),
    ocsp_responses: Iterable[ocsp.OCSPResponse] = (),
) -> RevocationInfoBundle:
    """Assemble a :class:`RevocationInfoBundle` from a candidate cert chain.

    Arguments:
        signer_cert: the signature's signing certificate (leaf).
        intermediate_certs: additional intermediates in the chain.
        issuer_cert: the immediate issuer of ``signer_cert``. When
            omitted the issuer is inferred from ``intermediate_certs``
            via :func:`CertificateVerifier._find_issuer`.
        crls: pre-fetched :class:`cryptography.x509.CertificateRevocationList`
            instances covering the chain.
        ocsp_responses: pre-fetched :class:`cryptography.x509.ocsp.OCSPResponse`
            instances covering the chain.

    Returns:
        A :class:`RevocationInfoBundle` whose ``certs`` deduplicates
        the chain (leaf + intermediates + root) and whose ``crls`` /
        ``ocsps`` lists carry the supplied responses DER-encoded.
    """
    seen_serial: set[tuple[bytes, int]] = set()
    cert_blobs: list[bytes] = []

    def _add_cert(cert: x509.Certificate) -> None:
        # Dedup on (issuer-DN-DER, serial) — cheap and unique under PKIX.
        key = (cert.issuer.public_bytes(), cert.serial_number)
        if key in seen_serial:
            return
        seen_serial.add(key)
        cert_blobs.append(cert.public_bytes(Encoding.DER))

    _add_cert(signer_cert)
    pool = list(intermediate_certs)
    if issuer_cert is not None:
        _add_cert(issuer_cert)
        if issuer_cert not in pool:
            pool.append(issuer_cert)
    for inter in pool:
        _add_cert(inter)

    crl_blobs = [c.public_bytes(Encoding.DER) for c in crls]
    ocsp_blobs = [r.public_bytes(Encoding.DER) for r in ocsp_responses]

    return RevocationInfoBundle(
        certs=cert_blobs, crls=crl_blobs, ocsps=ocsp_blobs
    )


def build_synthetic_ocsp_response(
    *,
    subject_cert: x509.Certificate,
    issuer_cert: x509.Certificate,
    responder_cert: x509.Certificate,
    responder_key: CertificateIssuerPrivateKeyTypes,
    status: ocsp.OCSPCertStatus = ocsp.OCSPCertStatus.GOOD,
    this_update: _dt.datetime | None = None,
    next_update: _dt.datetime | None = None,
    algorithm: hashes.HashAlgorithm | None = None,
) -> ocsp.OCSPResponse:
    """Build a fully self-signed OCSP response for offline LTV testing.

    Mirrors the canonical PyCA ``cryptography`` OCSP-builder recipe.
    Callers integrating with a real responder use their own fetcher and
    pass the result straight into :func:`collect_revocation_info` via
    ``ocsp_responses=``.
    """
    if this_update is None:
        this_update = _dt.datetime.now(tz=_dt.UTC)
    if next_update is None:
        next_update = this_update + _dt.timedelta(days=1)
    if algorithm is None:
        algorithm = hashes.SHA256()

    builder = ocsp.OCSPResponseBuilder()
    builder = builder.add_response(
        cert=subject_cert,
        issuer=issuer_cert,
        algorithm=algorithm,
        cert_status=status,
        this_update=this_update,
        next_update=next_update,
        revocation_time=None,
        revocation_reason=None,
    ).responder_id(ocsp.OCSPResponderEncoding.HASH, responder_cert)
    return builder.sign(responder_key, hashes.SHA256())


def build_synthetic_crl(
    *,
    issuer_cert: x509.Certificate,
    issuer_key: CertificateIssuerPrivateKeyTypes,
    revoked_serials: Iterable[int] = (),
    this_update: _dt.datetime | None = None,
    next_update: _dt.datetime | None = None,
) -> x509.CertificateRevocationList:
    """Build a self-signed empty (or sparsely populated) CRL for offline
    LTV testing. Real-world callers wire their CA's CRL fetcher and
    forward the resulting :class:`CertificateRevocationList` straight
    into :func:`collect_revocation_info` via ``crls=``."""
    if this_update is None:
        this_update = _dt.datetime.now(tz=_dt.UTC)
    if next_update is None:
        next_update = this_update + _dt.timedelta(days=1)

    builder = (
        x509.CertificateRevocationListBuilder()
        .issuer_name(issuer_cert.subject)
        .last_update(this_update)
        .next_update(next_update)
    )
    for serial in revoked_serials:
        revoked = (
            x509.RevokedCertificateBuilder()
            .serial_number(serial)
            .revocation_date(this_update)
            .build()
        )
        builder = builder.add_revoked_certificate(revoked)
    return builder.sign(private_key=issuer_key, algorithm=hashes.SHA256())
