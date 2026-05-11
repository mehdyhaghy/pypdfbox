"""Tests for ``RevokedCertificateException``."""

from __future__ import annotations

import datetime as _dt

import pytest

from pypdfbox.examples.signature.cert.revoked_certificate_exception import (
    RevokedCertificateException,
)


def test_default_revocation_time_is_none():
    exc = RevokedCertificateException("oops")
    assert exc.get_revocation_time() is None
    assert str(exc) == "oops"


def test_revocation_time_round_trips():
    when = _dt.datetime(2024, 1, 1, tzinfo=_dt.UTC)
    exc = RevokedCertificateException("revoked", revocation_time=when)
    assert exc.get_revocation_time() == when


def test_is_subclass_of_exception():
    with pytest.raises(RevokedCertificateException):
        raise RevokedCertificateException("boom")
