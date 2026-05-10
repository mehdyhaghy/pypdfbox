"""Wave 1272: parity coverage for ``LZWFilter.create_initial_code_table``
and ``LZWFilter.do_lzw_decode`` static helpers."""

from __future__ import annotations

from io import BytesIO

from pypdfbox.filter.lzw_filter import CLEAR_TABLE, EOD, LZWFilter


def test_create_initial_code_table_has_258_entries() -> None:
    table = LZWFilter.create_initial_code_table()
    # 256 byte literals + CLEAR_TABLE (256) + EOD (257) placeholders.
    assert len(table) == 258
    assert all(table[i] == bytes((i,)) for i in range(256))
    assert table[CLEAR_TABLE] is None
    assert table[EOD] is None


def test_create_initial_code_table_is_independent() -> None:
    a = LZWFilter.create_initial_code_table()
    b = LZWFilter.create_initial_code_table()
    a.append(b"x")
    assert len(b) == 258


def test_do_lzw_decode_round_trips_through_encode() -> None:
    payload = b"abcabcabcabc"
    encoded = BytesIO()
    LZWFilter().encode(BytesIO(payload), encoded)
    encoded.seek(0)
    decoded = BytesIO()
    LZWFilter.do_lzw_decode(encoded, decoded, early_change=True)
    assert decoded.getvalue() == payload
