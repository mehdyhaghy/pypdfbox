"""Tests for the pypdfbox-only CMap enrichment surface.

Covers the helpers we layer on top of upstream parity:

* :meth:`CMap.has_unicode_mapping` (singular alias)
* :meth:`CMap.to_unicode` strict-mode raise
* :meth:`CMap.read_code` bytes-form returning ``(code, byte_length)``
* :meth:`CMap.code_length_at` first-byte → expected code length
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.fontbox.cmap import CMap, CMapMappingError, CodespaceRange


# ---------- has_unicode_mapping ----------


def test_has_unicode_mapping_false_on_empty() -> None:
    cmap = CMap()
    assert cmap.has_unicode_mapping() is False
    assert cmap.has_unicode_mappings() is False


def test_has_unicode_mapping_true_after_add() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"A", "Alpha")
    assert cmap.has_unicode_mapping() is True
    # Singular and plural forms agree.
    assert cmap.has_unicode_mapping() == cmap.has_unicode_mappings()


def test_has_unicode_mapping_ignores_cid_only() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")
    cmap.add_cid_mapping(b"\x00\x20", 32)
    # CID mapping alone doesn't count as a Unicode mapping.
    assert cmap.has_unicode_mapping() is False


# ---------- to_unicode strict mode ----------


def test_to_unicode_strict_returns_value_when_mapped() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"A", "Alpha")
    assert cmap.to_unicode(0x41, strict=True) == "Alpha"


def test_to_unicode_strict_raises_on_missing() -> None:
    cmap = CMap("MissingMap")
    cmap.add_base_font_character(b"A", "Alpha")
    with pytest.raises(CMapMappingError) as excinfo:
        cmap.to_unicode(0x42, strict=True)
    msg = str(excinfo.value)
    assert "0x42" in msg
    assert "MissingMap" in msg


def test_to_unicode_lenient_returns_none_on_missing() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"A", "Alpha")
    # Default behaviour preserved — no raise, returns None.
    assert cmap.to_unicode(0x42) is None
    assert cmap.to_unicode(0x42, strict=False) is None


def test_to_unicode_strict_is_keyerror_subclass() -> None:
    cmap = CMap()
    with pytest.raises(KeyError):
        cmap.to_unicode(0x99, strict=True)


def test_to_unicode_walks_byte_lengths_then_raises() -> None:
    cmap = CMap("X")
    # Only 2-byte mapping defined; 1-byte default lookup falls through.
    cmap.add_base_font_character(b"\x00\x41", "Alpha")
    assert cmap.to_unicode(0x41, strict=True) == "Alpha"  # walks 1->2
    with pytest.raises(CMapMappingError):
        cmap.to_unicode(0x99, strict=True)


# ---------- read_code (bytes form) ----------


def test_read_code_bytes_returns_code_and_length_one_byte() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\xff")
    code, length = cmap.read_code(b"\x41")
    assert (code, length) == (0x41, 1)


def test_read_code_bytes_two_byte_codespace() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")
    code, length = cmap.read_code(b"\x12\x34")
    assert (code, length) == (0x1234, 2)


def test_read_code_bytes_offset_walk() -> None:
    """Walk a buffer of three concatenated 2-byte codes."""
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")
    buf = b"\x12\x34\x56\x78\x9A\xBC"

    out: list[int] = []
    offset = 0
    while offset < len(buf):
        code, length = cmap.read_code(buf, offset=offset)
        if length == 0:
            break
        out.append(code)
        offset += length

    assert out == [0x1234, 0x5678, 0x9ABC]


def test_read_code_bytes_mixed_lengths_picks_shortest_matching() -> None:
    """Adobe-Japan1 style: 1-byte ASCII + 2-byte JIS leading bytes."""
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\x7f")  # 1-byte ASCII
    cmap.add_codespace_range(b"\x81\x40", b"\x9f\xfc")  # 2-byte JIS
    cmap.add_codespace_range(b"\xe0\x40", b"\xfc\xfc")  # 2-byte JIS upper

    # ASCII byte stays 1 byte.
    assert cmap.read_code(b"\x41\x42") == (0x41, 1)
    # JIS leading byte triggers 2-byte read.
    assert cmap.read_code(b"\x81\x40") == (0x8140, 2)
    # And the upper-half range too.
    assert cmap.read_code(b"\xe0\x40") == (0xE040, 2)


def test_read_code_bytes_at_codespace_boundary() -> None:
    """Boundaries — start and end values inclusive — must match."""
    cmap = CMap()
    cmap.add_codespace_range(b"\x10", b"\x20")
    cmap.add_codespace_range(b"\x30\x00", b"\x40\xff")

    # Inside the 1-byte range.
    assert cmap.read_code(b"\x10") == (0x10, 1)
    assert cmap.read_code(b"\x20") == (0x20, 1)
    # Inside the 2-byte range.
    assert cmap.read_code(b"\x30\x00") == (0x3000, 2)
    assert cmap.read_code(b"\x40\xff") == (0x40FF, 2)


def test_read_code_bytes_truncated_tail_returns_partial() -> None:
    """If the trailing bytes are too short, we still return what we have."""
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")
    # Only one byte but min_code_length is 2.
    code, length = cmap.read_code(b"\xab")
    assert length == 1
    assert code == 0xAB


def test_read_code_bytes_empty_buffer_returns_zero_zero() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")
    assert cmap.read_code(b"") == (0, 0)


def test_read_code_bytes_no_codespace_falls_back_to_one_byte() -> None:
    cmap = CMap()  # No codespace ranges.
    assert cmap.read_code(b"\x7f") == (0x7F, 1)
    assert cmap.read_code(b"") == (0, 0)


def test_read_code_bytes_offset_out_of_range_raises() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\xff")
    with pytest.raises(ValueError):
        cmap.read_code(b"\x41", offset=-1)
    with pytest.raises(ValueError):
        cmap.read_code(b"\x41", offset=99)


def test_read_code_offset_with_stream_rejected() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\xff")
    with pytest.raises(TypeError):
        cmap.read_code(io.BytesIO(b"\x41"), offset=2)


def test_read_code_stream_form_still_returns_int() -> None:
    """Backward-compat — old stream-based callers must keep working."""
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")
    result = cmap.read_code(io.BytesIO(b"\x12\x34"))
    assert isinstance(result, int)
    assert result == 0x1234


# ---------- code_length_at ----------


def test_code_length_at_returns_none_without_codespaces() -> None:
    cmap = CMap()
    assert cmap.code_length_at(0x00) is None
    assert cmap.code_length_at(0xFF) is None


def test_code_length_at_simple_one_byte() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\xff")
    for b in (0x00, 0x41, 0xFF):
        assert cmap.code_length_at(b) == 1


def test_code_length_at_two_byte_only() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")
    assert cmap.code_length_at(0x00) == 2
    assert cmap.code_length_at(0x80) == 2


def test_code_length_at_adobe_japan1_style() -> None:
    """Mixed 1-byte / 2-byte leading-byte detection."""
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\x7f")
    cmap.add_codespace_range(b"\x81\x40", b"\x9f\xfc")
    cmap.add_codespace_range(b"\xe0\x40", b"\xfc\xfc")

    # ASCII zone -> 1.
    assert cmap.code_length_at(0x00) == 1
    assert cmap.code_length_at(0x7F) == 1
    # JIS zone -> 2.
    assert cmap.code_length_at(0x81) == 2
    assert cmap.code_length_at(0x9F) == 2
    assert cmap.code_length_at(0xE0) == 2
    assert cmap.code_length_at(0xFC) == 2
    # Outside any range -> None.
    assert cmap.code_length_at(0x80) is None
    assert cmap.code_length_at(0xA0) is None
    assert cmap.code_length_at(0xFD) is None


def test_code_length_at_picks_shortest_when_overlapping() -> None:
    """When 1-byte and 2-byte ranges overlap on the leading byte, the
    shortest match wins — that's what the parser commits to first."""
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\x7f")
    cmap.add_codespace_range(b"\x40\x00", b"\x7f\xff")  # overlaps 0x40-0x7F

    assert cmap.code_length_at(0x40) == 1
    assert cmap.code_length_at(0x7F) == 1
    assert cmap.code_length_at(0x80) is None


def test_code_length_at_masks_high_byte() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\xff")
    # Values above 0xFF are masked down.
    assert cmap.code_length_at(0x141) == 1
    assert cmap.code_length_at(0xFF | 0x100) == 1


def test_code_length_at_uses_codespace_ranges_via_use_cmap() -> None:
    """Codespaces inherited via ``use_cmap`` are visible to code_length_at."""
    base = CMap("Base")
    base.add_codespace_range(b"\x00", b"\x7f")
    base.add_codespace_range(b"\x81\x40", b"\x9f\xfc")

    child = CMap("Child")
    child.use_cmap(base)

    assert child.code_length_at(0x00) == 1
    assert child.code_length_at(0x81) == 2


# ---------- mixed: read_code_bytes + code_length_at consistency ----------


def test_read_code_byte_length_matches_code_length_at() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\x7f")
    cmap.add_codespace_range(b"\x81\x40", b"\x9f\xfc")

    for first_byte in (0x41, 0x81, 0x9F):
        expected = cmap.code_length_at(first_byte)
        # Pad with 0x40 so the 2-byte range matches.
        buf = bytes([first_byte, 0x40])
        _, length = cmap.read_code(buf)
        assert length == expected


# ---------- has_cid_mapping (singular alias) ----------


def test_has_cid_mapping_false_on_empty() -> None:
    cmap = CMap()
    assert cmap.has_cid_mapping() is False
    assert cmap.has_cid_mappings() is False


def test_has_cid_mapping_true_after_add_cid_mapping() -> None:
    cmap = CMap()
    cmap.add_cid_mapping(b"\x00\x20", 32)
    assert cmap.has_cid_mapping() is True
    # Singular and plural forms agree.
    assert cmap.has_cid_mapping() == cmap.has_cid_mappings()


def test_has_cid_mapping_true_after_add_cid_range() -> None:
    cmap = CMap()
    cmap.add_cid_range(b"\x00\x00", b"\x00\x10", cid=100)
    assert cmap.has_cid_mapping() is True


def test_has_cid_mapping_ignores_unicode_only() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"A", "Alpha")
    # Unicode mapping alone doesn't count as a CID mapping.
    assert cmap.has_cid_mapping() is False


# ---------- to_unicode_with_length (public 2-arg overload) ----------


def test_to_unicode_with_length_one_byte() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"A", "Alpha")
    assert cmap.to_unicode_with_length(0x41, 1) == "Alpha"


def test_to_unicode_with_length_two_bytes_ignores_one_byte_dict() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"\x00\x41", "TwoByteA")
    cmap.add_base_font_character(b"A", "OneByteA")
    # Same int 0x41 maps differently depending on the explicit byte length.
    assert cmap.to_unicode_with_length(0x41, 1) == "OneByteA"
    assert cmap.to_unicode_with_length(0x41, 2) == "TwoByteA"


def test_to_unicode_with_length_three_and_four_bytes() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"\xab\xcd\xef", "ThreeByte")
    cmap.add_base_font_character(b"\x12\x34\x56\x78", "FourByte")
    # 3- and 4-byte mappings share the same "more bytes" dict but
    # use distinct integer keys, so both round-trip cleanly.
    assert cmap.to_unicode_with_length(0xABCDEF, 3) == "ThreeByte"
    assert cmap.to_unicode_with_length(0x12345678, 4) == "FourByte"


def test_to_unicode_with_length_returns_none_when_unmapped() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"A", "Alpha")
    assert cmap.to_unicode_with_length(0x42, 1) is None
    assert cmap.to_unicode_with_length(0x41, 2) is None


def test_to_unicode_delegates_to_to_unicode_with_length() -> None:
    cmap = CMap()
    cmap.add_base_font_character(b"\x00\x41", "TwoByte")
    # 1-byte lookup miss falls through to the 2-byte attempt.
    assert cmap.to_unicode(0x41) == "TwoByte"
    # And the explicit 2-byte form returns the same value.
    assert cmap.to_unicode_with_length(0x41, 2) == "TwoByte"


# ---------- is_horizontal / is_vertical writing-mode predicates ----------


def test_is_horizontal_default_true() -> None:
    cmap = CMap()
    # WMode initialises to 0 (horizontal).
    assert cmap.get_wmode() == 0
    assert cmap.is_horizontal() is True
    assert cmap.is_vertical() is False


def test_is_vertical_after_set_wmode() -> None:
    cmap = CMap()
    cmap.set_wmode(1)
    assert cmap.is_vertical() is True
    assert cmap.is_horizontal() is False


def test_horizontal_and_vertical_are_mutually_exclusive() -> None:
    cmap = CMap()
    for wmode in (0, 1):
        cmap.set_wmode(wmode)
        assert cmap.is_horizontal() != cmap.is_vertical()


def test_unusual_wmode_values_treated_as_horizontal() -> None:
    """WMode is documented as 0 or 1; any other value falls back to
    horizontal (matching upstream's lenient handling)."""
    cmap = CMap()
    cmap.set_wmode(2)
    assert cmap.is_horizontal() is True
    assert cmap.is_vertical() is False
    cmap.set_wmode(-1)
    assert cmap.is_horizontal() is True
    assert cmap.is_vertical() is False


# ---------- code / cid length accessors ----------


def test_min_max_code_length_defaults_on_empty_cmap() -> None:
    cmap = CMap()
    # Defaults match upstream's pre-add initial values.
    assert cmap.get_min_code_length() == 4
    assert cmap.get_max_code_length() == 0


def test_min_max_cid_length_defaults_on_empty_cmap() -> None:
    cmap = CMap()
    assert cmap.get_min_cid_length() == 4
    assert cmap.get_max_cid_length() == 0


def test_code_length_tracks_added_codespace_ranges() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00\x00", b"\xff\xff")
    assert cmap.get_min_code_length() == 2
    assert cmap.get_max_code_length() == 2

    # Adding a 1-byte range lowers the minimum but the maximum stays at 2.
    cmap.add_codespace_range(b"\x00", b"\x7f")
    assert cmap.get_min_code_length() == 1
    assert cmap.get_max_code_length() == 2

    # And a 4-byte range raises the maximum.
    cmap.add_codespace_range(b"\x00\x00\x00\x00", b"\xff\xff\xff\xff")
    assert cmap.get_min_code_length() == 1
    assert cmap.get_max_code_length() == 4


def test_cid_length_tracks_added_cid_mappings() -> None:
    cmap = CMap()
    cmap.add_cid_mapping(b"\x00\x20", 32)
    assert cmap.get_min_cid_length() == 2
    assert cmap.get_max_cid_length() == 2

    # 3-byte CID raises the maximum.
    cmap.add_cid_mapping(b"\x00\x00\x20", 64)
    assert cmap.get_min_cid_length() == 2
    assert cmap.get_max_cid_length() == 3

    # 1-byte CID lowers the minimum.
    cmap.add_cid_mapping(b"\x20", 96)
    assert cmap.get_min_cid_length() == 1


def test_cid_length_tracks_added_cid_ranges() -> None:
    cmap = CMap()
    cmap.add_cid_range(b"\x00\x00", b"\x00\x10", cid=100)
    assert cmap.get_min_cid_length() == 2
    assert cmap.get_max_cid_length() == 2


def test_lengths_track_use_cmap() -> None:
    base = CMap("Base")
    base.add_codespace_range(b"\x00", b"\x7f")
    base.add_codespace_range(b"\x81\x40", b"\x9f\xfc")
    base.add_cid_mapping(b"\x00\x20", 32)

    child = CMap("Child")
    child.use_cmap(base)
    assert child.get_min_code_length() == 1
    assert child.get_max_code_length() == 2
    assert child.get_min_cid_length() == 2
    assert child.get_max_cid_length() == 2


# ---------- get_codespace_ranges ----------


def test_get_codespace_ranges_empty_cmap() -> None:
    cmap = CMap()
    assert cmap.get_codespace_ranges() == []


def test_get_codespace_ranges_returns_fresh_list() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\x7f")
    a = cmap.get_codespace_ranges()
    b = cmap.get_codespace_ranges()
    assert a == b
    assert a is not b
    # Mutating the returned list doesn't affect the CMap.
    a.append(CodespaceRange(b"\xff", b"\xff"))
    assert len(cmap.get_codespace_ranges()) == 1


def test_get_codespace_ranges_preserves_insertion_order() -> None:
    cmap = CMap()
    cmap.add_codespace_range(b"\x00", b"\x7f")
    cmap.add_codespace_range(b"\x81\x40", b"\x9f\xfc")
    cmap.add_codespace_range(b"\xe0\x40", b"\xfc\xfc")

    ranges = cmap.get_codespace_ranges()
    assert len(ranges) == 3
    assert ranges[0] == CodespaceRange(b"\x00", b"\x7f")
    assert ranges[1] == CodespaceRange(b"\x81\x40", b"\x9f\xfc")
    assert ranges[2] == CodespaceRange(b"\xe0\x40", b"\xfc\xfc")


def test_get_codespace_ranges_after_use_cmap() -> None:
    base = CMap("Base")
    base.add_codespace_range(b"\x00", b"\x7f")

    child = CMap("Child")
    child.add_codespace_range(b"\xa0", b"\xff")
    child.use_cmap(base)

    ranges = child.get_codespace_ranges()
    assert len(ranges) == 2
    # Original (child) range first, then the inherited one.
    assert ranges[0] == CodespaceRange(b"\xa0", b"\xff")
    assert ranges[1] == CodespaceRange(b"\x00", b"\x7f")
