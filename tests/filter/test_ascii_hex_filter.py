"""
Hand-written tests for the upstream-named :class:`ASCIIHexFilter` alias.

The full codec is exercised by ``test_ascii_hex_decode.py``; this module
verifies wiring and cross-instance interoperability.
"""

from __future__ import annotations

from io import BytesIO

from pypdfbox.cos import COSName
from pypdfbox.filter import ASCIIHexDecode, ASCIIHexFilter, FilterFactory
from pypdfbox.filter.ascii_hex_filter import (
    ASCIIHexFilter as DirectASCIIHexFilter,
)


def _round_trip(f: ASCIIHexDecode, data: bytes) -> bytes:
    enc = BytesIO()
    f.encode(BytesIO(data), enc, None)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, None)
    return dec.getvalue()


def test_ascii_hex_filter_is_ascii_hex_decode_subclass() -> None:
    assert issubclass(ASCIIHexFilter, ASCIIHexDecode)


def test_ascii_hex_filter_imports_from_package() -> None:
    assert ASCIIHexFilter is DirectASCIIHexFilter


def test_factory_resolves_ascii_hex_filter_long_name() -> None:
    inst = FilterFactory.get("ASCIIHexFilter")
    assert isinstance(inst, ASCIIHexFilter)


def test_factory_resolves_ascii_hex_filter_via_cosname() -> None:
    inst = FilterFactory.get(COSName.get_pdf_name("ASCIIHexFilter"))
    assert isinstance(inst, ASCIIHexFilter)


def test_factory_ascii_hex_decode_unchanged() -> None:
    long_filter = FilterFactory.get("ASCIIHexDecode")
    short_filter = FilterFactory.get("AHx")
    assert isinstance(long_filter, ASCIIHexDecode)
    assert long_filter is short_filter


def test_round_trip_through_ascii_hex_filter() -> None:
    payload = b"the quick brown fox jumps over the lazy dog"
    assert _round_trip(ASCIIHexFilter(), payload) == payload


def test_cross_class_round_trip_filter_then_decode() -> None:
    payload = bytes(range(256))
    enc = BytesIO()
    ASCIIHexFilter().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    ASCIIHexDecode().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_cross_class_round_trip_decode_then_filter() -> None:
    payload = b"reverse-direction check"
    enc = BytesIO()
    ASCIIHexDecode().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    ASCIIHexFilter().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_factory_is_registered_ascii_hex_filter() -> None:
    assert FilterFactory.is_registered("ASCIIHexFilter")
