"""
Hand-written tests for the upstream-named :class:`LZWFilter` alias.

The full LZW codec is exercised by ``test_lzw_decode.py``; this module
covers only the wiring guarantees specific to the alias module:

* ``LZWFilter`` is importable from ``pypdfbox.filter`` and from
  ``pypdfbox.filter.lzw_filter`` and is a subclass of ``LZWDecode``.
* ``FilterFactory.get("LZWFilter")`` resolves to a ``LZWFilter``
  instance distinct from but interoperable with the existing
  ``LZWDecode`` registration.
* A round-trip through ``LZWFilter`` produces the same bytes as a
  round-trip through ``LZWDecode`` (mixed instance compatibility).
"""

from __future__ import annotations

import random
from io import BytesIO

from pypdfbox.cos import COSName
from pypdfbox.filter import FilterFactory, LZWDecode, LZWFilter
from pypdfbox.filter.lzw_filter import (
    CLEAR_TABLE,
    EOD,
    MAX_TABLE_SIZE,
)
from pypdfbox.filter.lzw_filter import LZWFilter as DirectLZWFilter


def _round_trip(f: LZWDecode, data: bytes) -> bytes:
    enc = BytesIO()
    f.encode(BytesIO(data), enc, None)
    dec = BytesIO()
    f.decode(BytesIO(enc.getvalue()), dec, None)
    return dec.getvalue()


def test_lzw_filter_is_lzw_decode_subclass() -> None:
    assert issubclass(LZWFilter, LZWDecode)


def test_lzw_filter_imports_from_package() -> None:
    assert LZWFilter is DirectLZWFilter


def test_lzw_filter_constants_re_exported() -> None:
    assert CLEAR_TABLE == 256
    assert EOD == 257
    assert MAX_TABLE_SIZE == 4096


def test_factory_resolves_lzw_filter_long_name() -> None:
    inst = FilterFactory.get("LZWFilter")
    assert isinstance(inst, LZWFilter)


def test_factory_resolves_lzw_filter_via_cosname() -> None:
    inst = FilterFactory.get(COSName.get_pdf_name("LZWFilter"))
    assert isinstance(inst, LZWFilter)


def test_factory_lzw_decode_unchanged() -> None:
    # Adding the LZWFilter registration must not steal the existing
    # short-name "LZW" or long-name "LZWDecode" mapping.
    inst = FilterFactory.get("LZWDecode")
    assert isinstance(inst, LZWDecode)
    short = FilterFactory.get("LZW")
    assert isinstance(short, LZWDecode)


def test_round_trip_through_lzw_filter() -> None:
    payload = b"the quick brown fox jumps over the lazy dog\n" * 50
    assert _round_trip(LZWFilter(), payload) == payload


def test_round_trip_random_through_lzw_filter() -> None:
    rng = random.Random(0xCAFE)
    data = bytes(rng.randrange(256) for _ in range(8000))
    assert _round_trip(LZWFilter(), data) == data


def test_cross_class_round_trip_lzw_filter_then_lzw_decode() -> None:
    payload = b"cross-class compatibility check\n" * 25
    enc = BytesIO()
    LZWFilter().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    LZWDecode().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_cross_class_round_trip_lzw_decode_then_lzw_filter() -> None:
    payload = b"reverse-direction check\n" * 25
    enc = BytesIO()
    LZWDecode().encode(BytesIO(payload), enc, None)
    dec = BytesIO()
    LZWFilter().decode(BytesIO(enc.getvalue()), dec, None)
    assert dec.getvalue() == payload


def test_factory_is_registered_lzw_filter() -> None:
    assert FilterFactory.is_registered("LZWFilter")
