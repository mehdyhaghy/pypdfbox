"""
Hand-written tests for the upstream-named :class:`ASCII85Filter` alias.

The full codec is exercised by ``test_ascii85_decode.py``; this module
verifies wiring and cross-instance interoperability.
"""

from __future__ import annotations

from io import BytesIO

from pypdfbox.cos import COSName
from pypdfbox.filter import ASCII85Decode, ASCII85Filter, FilterFactory
from pypdfbox.filter.ascii85_filter import ASCII85Filter as DirectASCII85Filter


def _round_trip(f: ASCII85Decode, data: bytes) -> bytes:
    enc = BytesIO()
    f.encode(BytesIO(data), enc, None)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, None)
    return dec.getvalue()


def test_ascii85_filter_is_ascii85_decode_subclass() -> None:
    assert issubclass(ASCII85Filter, ASCII85Decode)


def test_ascii85_filter_imports_from_package() -> None:
    assert ASCII85Filter is DirectASCII85Filter


def test_factory_resolves_ascii85_filter_long_name() -> None:
    inst = FilterFactory.get("ASCII85Filter")
    assert isinstance(inst, ASCII85Filter)


def test_factory_resolves_ascii85_filter_via_cosname() -> None:
    inst = FilterFactory.get(COSName.get_pdf_name("ASCII85Filter"))
    assert isinstance(inst, ASCII85Filter)


def test_factory_ascii85_decode_unchanged() -> None:
    long_filter = FilterFactory.get("ASCII85Decode")
    short_filter = FilterFactory.get("A85")
    assert isinstance(long_filter, ASCII85Decode)
    assert long_filter is short_filter


def test_round_trip_through_ascii85_filter() -> None:
    payload = b"the quick brown fox jumps over the lazy dog\n" * 20
    assert _round_trip(ASCII85Filter(), payload) == payload


def test_cross_class_round_trip_filter_then_decode() -> None:
    payload = bytes(range(256))
    enc = BytesIO()
    ASCII85Filter().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    ASCII85Decode().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_cross_class_round_trip_decode_then_filter() -> None:
    payload = b"reverse-direction check\n" * 25
    enc = BytesIO()
    ASCII85Decode().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    ASCII85Filter().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_factory_is_registered_ascii85_filter() -> None:
    assert FilterFactory.is_registered("ASCII85Filter")
