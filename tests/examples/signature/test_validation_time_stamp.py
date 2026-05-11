"""Tests for ``ValidationTimeStamp``."""

from __future__ import annotations

from io import BytesIO

import pytest

from pypdfbox.examples.signature.validation_time_stamp import ValidationTimeStamp


def test_no_tsa_url_means_no_client():
    vts = ValidationTimeStamp(None)
    with pytest.raises(ValueError):
        vts.get_time_stamp_token(BytesIO(b""))


def test_round_trips_through_transport():
    def fake_transport(request, url, headers):
        return b"DEADBEEF"

    vts = ValidationTimeStamp("http://tsa.test.invalid", transport=fake_transport)
    assert vts.get_time_stamp_token(BytesIO(b"abc")) == b"DEADBEEF"


def test_add_signed_time_stamp_appends_token():
    def fake_transport(request, url, headers):
        return b"TOK"

    vts = ValidationTimeStamp("http://tsa.test.invalid", transport=fake_transport)
    new_blob = vts.add_signed_time_stamp(b"signed")
    assert new_blob == b"signedTOK"


def test_add_signed_time_stamp_without_tsa_is_passthrough():
    vts = ValidationTimeStamp(None)
    assert vts.add_signed_time_stamp(b"signed") == b"signed"
