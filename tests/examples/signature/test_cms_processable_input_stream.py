"""Tests for ``CMSProcessableInputStream``."""

from __future__ import annotations

from io import BytesIO

from pypdfbox.examples.signature.cms_processable_input_stream import (
    CMSProcessableInputStream,
)


def test_default_content_type_is_id_data():
    wrapper = CMSProcessableInputStream(BytesIO(b""))
    assert wrapper.get_content_type() == "1.2.840.113549.1.7.1"


def test_get_content_returns_underlying_stream():
    payload = BytesIO(b"hello")
    wrapper = CMSProcessableInputStream(payload)
    assert wrapper.get_content() is payload


def test_write_copies_and_closes_source():
    payload = BytesIO(b"hello world")
    out = BytesIO()
    wrapper = CMSProcessableInputStream(payload)
    wrapper.write(out)
    assert out.getvalue() == b"hello world"
    assert payload.closed is True


def test_custom_content_type_round_trips():
    wrapper = CMSProcessableInputStream(BytesIO(b""), content_type="1.2.3.4")
    assert wrapper.get_content_type() == "1.2.3.4"
