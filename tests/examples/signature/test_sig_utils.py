"""Tests for ``SigUtils``."""

from __future__ import annotations

import pytest

from pypdfbox.examples.signature.sig_utils import SigUtils


def test_static_helper_cannot_be_instantiated():
    with pytest.raises(RuntimeError):
        SigUtils()


def test_check_certificate_usage_accepts_signing_cert(self_signed_cert, caplog):
    cert, _ = self_signed_cert
    caplog.clear()
    SigUtils.check_certificate_usage(cert)
    assert not [r for r in caplog.records if r.levelname == "ERROR"]


def test_check_time_stamp_usage_logs_for_non_timestamp_cert(
    self_signed_cert, caplog
):
    cert, _ = self_signed_cert
    with caplog.at_level("ERROR"):
        SigUtils.check_time_stamp_certificate_usage(cert)
    assert any("timeStamping" in r.message for r in caplog.records)


def test_check_responder_usage_logs_for_non_ocsp_cert(
    self_signed_cert, caplog
):
    cert, _ = self_signed_cert
    with caplog.at_level("ERROR"):
        SigUtils.check_responder_certificate_usage(cert)
    assert any("OCSP" in r.message for r in caplog.records)
