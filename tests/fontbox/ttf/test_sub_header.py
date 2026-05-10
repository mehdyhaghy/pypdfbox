"""Tests for :class:`pypdfbox.fontbox.ttf.sub_header.SubHeader`."""

from __future__ import annotations

from pypdfbox.fontbox.ttf.sub_header import SubHeader


def test_default_constructor_zero_filled() -> None:
    sh = SubHeader()
    assert sh.get_first_code() == 0
    assert sh.get_entry_count() == 0
    assert sh.get_id_delta() == 0
    assert sh.get_id_range_offset() == 0


def test_accessors_match_constructor_args() -> None:
    sh = SubHeader(first_code=0x41, entry_count=26, id_delta=-3, id_range_offset=12)
    assert sh.get_first_code() == 0x41
    assert sh.get_entry_count() == 26
    assert sh.get_id_delta() == -3
    assert sh.get_id_range_offset() == 12


def test_subheader_is_frozen() -> None:
    import dataclasses

    sh = SubHeader(1, 2, 3, 4)
    try:
        sh.first_code = 99  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("SubHeader must be frozen — upstream final fields")


def test_negative_id_delta_preserved() -> None:
    # id_delta is signed int16 upstream; negative values must round-trip.
    sh = SubHeader(id_delta=-32768)
    assert sh.get_id_delta() == -32768


def test_glyph_index_arithmetic_mod_65536() -> None:
    # Smoke-check: (p + id_delta) mod 65536 is well-defined for the full
    # signed-int16 range upstream supports.
    sh = SubHeader(id_delta=-1)
    p = 0
    assert (p + sh.get_id_delta()) % 65536 == 65535
