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
