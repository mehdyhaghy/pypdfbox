"""Tests for :mod:`pypdfbox.examples.signature.cert.revocation_collector`.

Covers the three helpers exposed for offline LTV-bundle assembly:

* :func:`collect_revocation_info` — chain dedup + DER encoding of supplied
  CRLs and OCSP responses.
* :func:`build_synthetic_ocsp_response` — self-issued OCSP responder
  recipe used by tests and closed-ecosystem callers.
* :func:`build_synthetic_crl` — self-signed (optionally populated) CRL
  for offline LTV verification.

The module ships no CLI; it is a library helper imported by callers
wiring LTV bundles. Tests therefore exercise the API directly.
"""

from __future__ import annotations

import datetime as _dt

from cryptography.x509 import ocsp

from pypdfbox.examples.signature.cert.revocation_collector import (
    RevocationInfoBundle,
    build_synthetic_crl,
    build_synthetic_ocsp_response,
    collect_revocation_info,
)


def test_collect_revocation_info_only_signer(self_signed_cert) -> None:
    """Bare signer cert with no chain → one cert blob, empty crls/ocsps."""
    cert, _ = self_signed_cert
    bundle = collect_revocation_info(cert)
    assert isinstance(bundle, RevocationInfoBundle)
    assert len(bundle.certs) == 1
    assert bundle.crls == []
    assert bundle.ocsps == []
    assert bundle.is_empty() is False


def test_collect_revocation_info_dedups_chain(self_signed_cert) -> None:
    """Passing the same issuer twice (via ``issuer_cert`` + intermediates)
    must not produce a duplicate blob."""
    cert, _ = self_signed_cert
    bundle = collect_revocation_info(
        cert,
        intermediate_certs=[cert],
        issuer_cert=cert,
    )
    # signer + issuer/intermediate dedup → still 1 unique cert blob.
    assert len(bundle.certs) == 1


def test_collect_revocation_info_carries_crls_and_ocsp(
    self_signed_cert,
) -> None:
    """Supplied CRLs and OCSP responses are DER-encoded and forwarded."""
    cert, key = self_signed_cert
    crl = build_synthetic_crl(issuer_cert=cert, issuer_key=key)
    ocsp_resp = build_synthetic_ocsp_response(
        subject_cert=cert,
        issuer_cert=cert,
        responder_cert=cert,
        responder_key=key,
    )
    bundle = collect_revocation_info(
        cert, crls=[crl], ocsp_responses=[ocsp_resp]
    )
    assert len(bundle.certs) == 1
    assert len(bundle.crls) == 1
    assert len(bundle.ocsps) == 1
    # Round-trip the DER blobs to prove they parse back.
    from cryptography import x509

    parsed_crl = x509.load_der_x509_crl(bundle.crls[0])
    assert parsed_crl.issuer == cert.subject
    parsed_ocsp = ocsp.load_der_ocsp_response(bundle.ocsps[0])
    assert parsed_ocsp.response_status == ocsp.OCSPResponseStatus.SUCCESSFUL


def test_bundle_is_empty_for_default() -> None:
    """An entirely empty bundle reports ``is_empty()``."""
    assert RevocationInfoBundle(certs=[], crls=[], ocsps=[]).is_empty() is True


def test_build_synthetic_crl_with_revoked_serials(self_signed_cert) -> None:
    """Populating ``revoked_serials`` produces a CRL with those entries."""
    cert, key = self_signed_cert
    crl = build_synthetic_crl(
        issuer_cert=cert,
        issuer_key=key,
        revoked_serials=[42, 1337],
    )
    revoked_serials = {entry.serial_number for entry in crl}
    assert revoked_serials == {42, 1337}


def test_build_synthetic_ocsp_response_status_good(self_signed_cert) -> None:
    """Default ``status`` is GOOD."""
    cert, key = self_signed_cert
    resp = build_synthetic_ocsp_response(
        subject_cert=cert,
        issuer_cert=cert,
        responder_cert=cert,
        responder_key=key,
    )
    assert resp.response_status == ocsp.OCSPResponseStatus.SUCCESSFUL
    assert resp.certificate_status == ocsp.OCSPCertStatus.GOOD


def test_build_synthetic_ocsp_response_honours_explicit_dates(
    self_signed_cert,
) -> None:
    """Explicit ``this_update`` / ``next_update`` flow into the response."""
    cert, key = self_signed_cert
    this_update = _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
    next_update = this_update + _dt.timedelta(days=7)
    resp = build_synthetic_ocsp_response(
        subject_cert=cert,
        issuer_cert=cert,
        responder_cert=cert,
        responder_key=key,
        this_update=this_update,
        next_update=next_update,
    )
    # Use the aware ``_utc`` accessors (cryptography deprecated the naive ones).
    assert resp.this_update_utc == this_update
    assert resp.next_update_utc == next_update
