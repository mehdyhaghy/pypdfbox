"""
Hand-written tests for the upstream-named :class:`FlateFilter` alias.

The full codec is exercised by ``test_flate_decode.py``; this module
verifies wiring and cross-instance interoperability.
"""

from __future__ import annotations

from io import BytesIO

from pypdfbox.cos import COSName
from pypdfbox.filter import FilterFactory, FlateDecode, FlateFilter
from pypdfbox.filter.flate_filter import FlateFilter as DirectFlateFilter


def _round_trip(f: FlateDecode, data: bytes) -> bytes:
    enc = BytesIO()
    f.encode(BytesIO(data), enc, None)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, None)
    return dec.getvalue()


def test_flate_filter_is_flate_decode_subclass() -> None:
    assert issubclass(FlateFilter, FlateDecode)


def test_flate_filter_imports_from_package() -> None:
    assert FlateFilter is DirectFlateFilter


def test_factory_resolves_flate_filter_long_name() -> None:
    inst = FilterFactory.get("FlateFilter")
    assert isinstance(inst, FlateFilter)


def test_factory_resolves_flate_filter_via_cosname() -> None:
    inst = FilterFactory.get(COSName.get_pdf_name("FlateFilter"))
    assert isinstance(inst, FlateFilter)


def test_factory_flate_decode_unchanged() -> None:
    long_filter = FilterFactory.get("FlateDecode")
    short_filter = FilterFactory.get("Fl")
    assert isinstance(long_filter, FlateDecode)
    assert long_filter is short_filter


def test_round_trip_through_flate_filter() -> None:
    payload = b"the quick brown fox jumps over the lazy dog\n" * 20
    assert _round_trip(FlateFilter(), payload) == payload


def test_cross_class_round_trip_filter_then_decode() -> None:
    payload = bytes(range(256))
    enc = BytesIO()
    FlateFilter().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    FlateDecode().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_cross_class_round_trip_decode_then_filter() -> None:
    payload = b"reverse-direction check\n" * 25
    enc = BytesIO()
    FlateDecode().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    FlateFilter().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_factory_is_registered_flate_filter() -> None:
    assert FilterFactory.is_registered("FlateFilter")
