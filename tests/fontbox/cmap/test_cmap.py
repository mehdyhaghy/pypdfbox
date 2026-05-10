from __future__ import annotations

import io

from pypdfbox.fontbox.cmap import CMap, CodespaceRange
from pypdfbox.io import RandomAccessReadBuffer


def test_empty_cmap_read_code_reads_one_byte_without_crashing() -> None:
    cmap = CMap()
    assert cmap.read_code(RandomAccessReadBuffer(b"\x7f")) == 0x7F
    assert cmap.read_code(io.BytesIO(b"")) == 0


def test_codespace_and_unicode_mapping_round_trip() -> None:
    cmap = CMap()
    cmap.add_codespace_range(CodespaceRange(b"\x00", b"\xff"))
    cmap.add_base_font_character(b"A", "Alpha")

    assert cmap.read_code(io.BytesIO(b"A")) == 0x41
    assert cmap.to_unicode(0x41) == "Alpha"
    assert cmap.to_unicode_bytes(b"A") == "Alpha"
    assert cmap.get_codes_from_unicode("Alpha") == b"A"


def test_cid_mapping_and_usecmap_copy() -> None:
    base = CMap("Base")
    base.add_codespace_range(b"\x00\x00", b"\xff\xff")
    base.add_cid_mapping(b"\x00\x20", 32)

    child = CMap("Child")
    child.use_cmap(base)

    assert child.read_cid(io.BytesIO(b"\x00\x20")) == 32


def test_add_char_mapping_is_alias_for_add_base_font_character() -> None:
    """``add_char_mapping`` is the camel-to-snake port of upstream
    ``CMap.addCharMapping`` — must produce the same Unicode mapping as
    the descriptive ``add_base_font_character`` synonym."""
    via_alias = CMap()
    via_alias.add_char_mapping(b"\x00\x41", "A")

    via_descriptive = CMap()
    via_descriptive.add_base_font_character(b"\x00\x41", "A")

    assert via_alias.to_unicode_bytes(b"\x00\x41") == "A"
    assert via_alias.get_codes_from_unicode("A") == b"\x00\x41"
    assert via_alias.to_unicode_bytes(b"\x00\x41") == via_descriptive.to_unicode_bytes(
        b"\x00\x41"
    )


def test_w_mode_canonical_and_synonym_stay_in_sync() -> None:
    """``get_w_mode``/``set_w_mode`` is the strict camel-to-snake port of
    ``getWMode``/``setWMode``. The pre-existing ``get_wmode``/``set_wmode``
    spelling is kept as an ergonomic synonym; both must observe the same
    underlying writing-mode field."""
    cmap = CMap()
    assert cmap.get_w_mode() == 0
    assert cmap.get_wmode() == 0

    cmap.set_w_mode(1)
    assert cmap.get_w_mode() == 1
    assert cmap.get_wmode() == 1
    assert cmap.is_vertical()

    cmap.set_wmode(0)
    assert cmap.get_w_mode() == 0
    assert cmap.is_horizontal()


def test_to_int_static_helper_matches_upstream() -> None:
    """``CMap.to_int`` is the port of upstream ``CMap.toInt(byte[])`` — a
    big-endian byte-array-to-int helper. The optional ``data_len`` argument
    mirrors the private two-arg upstream overload."""
    assert CMap.to_int(b"\x01\x02\x03\x04") == 0x01020304
    assert CMap.to_int(b"\x01\x02\x03\x04", 2) == 0x0102
    assert CMap.to_int(b"\xff") == 0xFF
    # High bit must NOT sign-extend (Java masks with & 0xFF; we must too).
    assert CMap.to_int(b"\x80\x00") == 0x8000


def test_to_string_returns_cmap_name() -> None:
    """``CMap.to_string()`` is the port of upstream ``CMap.toString()``;
    it must mirror ``__str__`` and return the bare CMap name (or empty
    string when unset)."""
    cmap = CMap()
    assert cmap.to_string() == ""
    assert str(cmap) == ""

    cmap.set_name("Adobe-Japan1-6")
    assert cmap.to_string() == "Adobe-Japan1-6"
    assert str(cmap) == "Adobe-Japan1-6"


def test_to_cid_from_ranges_int_and_bytes() -> None:
    """Public ``to_cid_from_ranges`` exposes the two private upstream
    helpers (``toCIDFromRanges(int, int)`` and ``toCIDFromRanges(byte[])``)
    as a single dispatch entry. Both forms must skip the direct
    ``codeToCid`` dicts and consult only the registered ranges."""
    cmap = CMap()
    cmap.add_cid_range(b"\x00\x00", b"\x00\xff", 100)

    # int form — requires the length argument.
    assert cmap.to_cid_from_ranges(0x0010, 2) == 100 + 0x10

    # bytes form — length is inferred from the byte sequence.
    assert cmap.to_cid_from_ranges(b"\x00\x10") == 100 + 0x10

    # Out-of-range codes return 0 (the standard "no mapping" sentinel).
    assert cmap.to_cid_from_ranges(b"\x01\x00") == 0

    import pytest

    with pytest.raises(TypeError):
        cmap.to_cid_from_ranges(0x10)  # int without length is invalid
