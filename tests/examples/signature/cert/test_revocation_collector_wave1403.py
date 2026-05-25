"""Wave 1403 branch round-out for ``revocation_collector``.

Drives the False arcs of the three ``is None`` default-value guards:

* ``132->135`` — ``build_synthetic_ocsp_response`` called with an explicit
  ``algorithm``.
* ``161->163`` — ``build_synthetic_crl`` called with an explicit
  ``this_update``.
* ``163->166`` — ``build_synthetic_crl`` called with an explicit
  ``next_update``.
"""

from __future__ import annotations

import datetime as _dt

from cryptography.hazmat.primitives import hashes
from cryptography.x509 import ocsp

from pypdfbox.examples.signature.cert.revocation_collector import (
    build_synthetic_crl,
    build_synthetic_ocsp_response,
)


def test_ocsp_response_with_explicit_algorithm(self_signed_cert) -> None:
    """Passing ``algorithm`` skips the default-SHA256 assignment (132->135)."""
    cert, key = self_signed_cert
    resp = build_synthetic_ocsp_response(
        subject_cert=cert,
        issuer_cert=cert,
        responder_cert=cert,
        responder_key=key,
        status=ocsp.OCSPCertStatus.GOOD,
        algorithm=hashes.SHA256(),
    )
    assert resp.response_status == ocsp.OCSPResponseStatus.SUCCESSFUL


def test_crl_with_explicit_this_update_only(self_signed_cert) -> None:
    """Explicit ``this_update`` (but default ``next_update``) drives the
    False arc of ``if this_update is None`` (161->163) while leaving the
    ``next_update`` default in play."""
    cert, key = self_signed_cert
    this_update = _dt.datetime(2024, 1, 1, tzinfo=_dt.UTC)
    crl = build_synthetic_crl(
        issuer_cert=cert,
        issuer_key=key,
        this_update=this_update,
    )
    assert crl.last_update_utc == this_update
    # next_update defaulted to this_update + 1 day.
    assert crl.next_update_utc == this_update + _dt.timedelta(days=1)


def test_crl_with_explicit_both_dates(self_signed_cert) -> None:
    """Explicit ``this_update`` and ``next_update`` drive both False arcs
    (161->163 and 163->166)."""
    cert, key = self_signed_cert
    this_update = _dt.datetime(2024, 6, 1, tzinfo=_dt.UTC)
    next_update = _dt.datetime(2024, 6, 15, tzinfo=_dt.UTC)
    crl = build_synthetic_crl(
        issuer_cert=cert,
        issuer_key=key,
        this_update=this_update,
        next_update=next_update,
    )
    assert crl.last_update_utc == this_update
    assert crl.next_update_utc == next_update
