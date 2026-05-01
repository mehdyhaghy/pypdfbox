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
from pypdfbox.filter.lzw_decode import _calculate_chunk
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


# ---------- upstream parity helpers (calculate_chunk / find_pattern_code /
# create_code_table) -------------------------------------------------------


def test_calculate_chunk_static_matches_module_helper() -> None:
    # Public static parity helper mirrors upstream LZWFilter#calculateChunk.
    # It should match the existing module-private helper across the full
    # 9..12-bit boundary set, with and without EarlyChange.
    for tab_size in (0, 511, 512, 1023, 1024, 2047, 2048, 4095):
        for early in (True, False):
            assert LZWFilter.calculate_chunk(tab_size, early) == _calculate_chunk(
                tab_size, early
            ), f"mismatch at tab_size={tab_size}, early={early}"


def test_calculate_chunk_known_boundaries_early_change() -> None:
    # EarlyChange=1: width grows when next code would be 511/1023/2047.
    assert LZWFilter.calculate_chunk(0, True) == 9
    assert LZWFilter.calculate_chunk(510, True) == 9
    assert LZWFilter.calculate_chunk(511, True) == 10
    assert LZWFilter.calculate_chunk(1023, True) == 11
    assert LZWFilter.calculate_chunk(2047, True) == 12


def test_create_code_table_seeds_literals_and_placeholders() -> None:
    table = LZWFilter.create_code_table()
    # 256 literal entries + CLEAR + EOD = 258 entries total.
    assert len(table) == 258
    for i in range(256):
        assert table[i] == bytes((i,)), f"entry {i} should be its byte literal"
    # Reserved slots are placeholders (None) — they must never match data.
    assert table[CLEAR_TABLE] is None
    assert table[EOD] is None


def test_create_code_table_returns_independent_copies() -> None:
    # Mirrors upstream's createCodeTable which returns a fresh ArrayList:
    # mutating one must not affect another.
    a = LZWFilter.create_code_table()
    b = LZWFilter.create_code_table()
    a.append(b"mutated")
    assert len(b) == 258
    assert b[-1] is None


def test_find_pattern_code_single_byte_returns_byte_value() -> None:
    table = LZWFilter.create_code_table()
    # Single-byte patterns short-circuit to the byte value itself.
    for i in (0, 1, 65, 200, 255):
        assert LZWFilter.find_pattern_code(table, bytes((i,))) == i


def test_find_pattern_code_multi_byte_match() -> None:
    table = LZWFilter.create_code_table()
    # Append a couple of synthetic multi-byte entries and verify lookup
    # returns the correct table index (entries before 258 are skipped).
    table.append(b"AB")  # index 258
    table.append(b"BA")  # index 259
    table.append(b"ABC")  # index 260
    assert LZWFilter.find_pattern_code(table, b"AB") == 258
    assert LZWFilter.find_pattern_code(table, b"BA") == 259
    assert LZWFilter.find_pattern_code(table, b"ABC") == 260


def test_find_pattern_code_no_match_returns_minus_one() -> None:
    table = LZWFilter.create_code_table()
    table.append(b"AB")
    assert LZWFilter.find_pattern_code(table, b"XY") == -1


def test_find_pattern_code_skips_reserved_slots() -> None:
    # Reserved indices 256/257 hold None; even if a caller asks for a
    # 2-byte pattern, those slots must not produce false hits.
    table = LZWFilter.create_code_table()
    # Sanity: the reserved slots are still None.
    assert table[256] is None and table[257] is None
    # Looking up a multi-byte pattern that doesn't exist should return
    # -1 without raising (i.e. the loop must not dereference None).
    assert LZWFilter.find_pattern_code(table, b"\x00\x01") == -1
