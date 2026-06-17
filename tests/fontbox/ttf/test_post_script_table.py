from __future__ import annotations

import struct
from dataclasses import dataclass

import pytest

from pypdfbox.fontbox.ttf import wgl4_names
from pypdfbox.fontbox.ttf.post_script_table import PostScriptTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


@dataclass
class _StubTTF:
    name: str = "TestFont"
    num_glyphs: int = 0

    def get_name(self) -> str:
        return self.name

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs


def _pack_fixed(whole: int, frac: int = 0) -> bytes:
    # signed-short whole, unsigned-short frac
    return struct.pack(">hH", whole, frac)


def _pack_header(
    fmt_whole: int,
    fmt_frac: int = 0,
    italic_whole: int = 0,
    italic_frac: int = 0,
    underline_pos: int = -100,
    underline_thick: int = 50,
    is_fixed_pitch: int = 0,
    min_mem42: int = 0,
    max_mem42: int = 0,
    min_mem1: int = 0,
    max_mem1: int = 0,
) -> bytes:
    return (
        _pack_fixed(fmt_whole, fmt_frac)
        + _pack_fixed(italic_whole, italic_frac)
        + struct.pack(">hh", underline_pos, underline_thick)
        + struct.pack(">IIIII", is_fixed_pitch, min_mem42, max_mem42, min_mem1, max_mem1)
    )


def _read(blob: bytes, ttf: _StubTTF | None = None) -> PostScriptTable:
    table = PostScriptTable()
    table.set_length(len(blob))
    table.read(ttf or _StubTTF(), MemoryTTFDataStream(blob))  # type: ignore[arg-type]
    return table


def test_header_only_no_glyph_names() -> None:
    blob = _pack_header(3, italic_whole=0, italic_frac=0,
                        underline_pos=-150, underline_thick=20,
                        is_fixed_pitch=1,
                        min_mem42=0x10, max_mem42=0x20,
                        min_mem1=0x30, max_mem1=0x40)
    t = _read(blob)
    assert t.get_format_type() == 3.0
    assert t.get_italic_angle() == 0.0
    assert t.get_underline_position() == -150
    assert t.get_underline_thickness() == 20
    assert t.get_is_fixed_pitch() == 1
    assert t.get_min_mem_type42() == 0x10
    assert t.get_max_mem_type42() == 0x20
    assert t.get_min_mem_type1() == 0x30
    assert t.get_max_mem_type1() == 0x40
    # No bytes left after the header — warning path; format 3.0 means no names anyway.
    assert t.get_glyph_names() is None
    assert t.get_initialized() is True


def test_format_1_uses_wgl4_names() -> None:
    # Format 1.0 with at least one extra byte after header so we don't trip
    # the EOF warning path.
    blob = _pack_header(1) + b"\x00"
    t = _read(blob)
    assert t.get_format_type() == 1.0
    names = t.get_glyph_names()
    assert names is not None
    assert len(names) == wgl4_names.NUMBER_OF_MAC_GLYPHS
    assert names[0] == ".notdef"
    assert names[3] == "space"
    # accessor
    assert t.get_name(0) == ".notdef"
    assert t.get_name(-1) is None
    assert t.get_name(len(names)) is None


def test_format_2_with_custom_names() -> None:
    # 3 glyphs: index 0 -> WGL4 ".notdef" (mac index 0)
    #           index 1 -> WGL4 "space"   (mac index 3)
    #           index 2 -> custom name "myGlyph" (index 258)
    num_glyphs = 3
    indices = [0, 3, wgl4_names.NUMBER_OF_MAC_GLYPHS]  # last refs custom slot 0
    body = struct.pack(">H", num_glyphs)
    body += b"".join(struct.pack(">H", i) for i in indices)
    # one custom Pascal-style name
    body += bytes([len("myGlyph")]) + b"myGlyph"

    blob = _pack_header(2) + body
    t = _read(blob)
    assert t.get_format_type() == 2.0
    names = t.get_glyph_names()
    assert names == [".notdef", "space", "myGlyph"]


def test_format_2_reserved_index_yields_undefined() -> None:
    # An index in 32768..65535 is reserved; should resolve to ".undefined".
    num_glyphs = 2
    body = struct.pack(">HHH", num_glyphs, 0, 40000)
    blob = _pack_header(2) + body
    t = _read(blob)
    names = t.get_glyph_names()
    assert names == [".notdef", ".undefined"]


def test_format_2_eof_reading_length_byte_raises() -> None:
    # Claim two custom names but write only the first ("abc") with NO trailing
    # bytes for the second entry's Pascal length byte. Upstream FontBox 3.0.7
    # wraps ONLY ``readString`` in the PDFBOX-4851 try/catch; the preceding
    # ``readUnsignedByte`` (the length) is OUTSIDE the guard, so an EOF reading
    # the length byte propagates as IOException/EOFException rather than padding
    # with .notdef. Verified BOTH-SIDES against the FontBox 3.0.7 oracle in
    # tests/fontbox/ttf/oracle/test_ttf_metric_table_fuzz_wave1553.py
    # (``post_eof_len_byte``). Retargeted in wave 1553 alongside the
    # post_script_table.py fix.
    num_glyphs = 2
    indices = [
        wgl4_names.NUMBER_OF_MAC_GLYPHS,        # custom slot 0
        wgl4_names.NUMBER_OF_MAC_GLYPHS + 1,    # custom slot 1
    ]
    body = struct.pack(">H", num_glyphs)
    body += b"".join(struct.pack(">H", i) for i in indices)
    body += bytes([3]) + b"abc"  # only first name supplied; no length byte after
    blob = _pack_header(2) + body
    with pytest.raises((OSError, EOFError)):
        _read(blob)


def test_format_2_truncated_string_bytes_pad_with_notdef() -> None:
    # When the Pascal LENGTH byte IS readable but the string BYTES run out, the
    # PDFBOX-4851 try/catch around ``readString`` fires and pads the remaining
    # entries with .notdef (verified against the FontBox 3.0.7 oracle: a length
    # byte of 5 with only 2 string bytes yields ["abc", ".notdef"]).
    num_glyphs = 2
    indices = [
        wgl4_names.NUMBER_OF_MAC_GLYPHS,        # custom slot 0
        wgl4_names.NUMBER_OF_MAC_GLYPHS + 1,    # custom slot 1
    ]
    body = struct.pack(">H", num_glyphs)
    body += b"".join(struct.pack(">H", i) for i in indices)
    body += bytes([3]) + b"abc"  # first name
    body += bytes([5]) + b"xy"   # second name claims 5 chars but supplies 2
    blob = _pack_header(2) + body
    t = _read(blob)
    names = t.get_glyph_names()
    assert names == ["abc", ".notdef"]


def test_format_2_5_uses_offsets() -> None:
    # Format 2.5: per-glyph signed byte offset; final index = i + 1 + offset
    # 3 glyphs, offsets chosen so that:
    #   gid 0 -> 0+1+(-1) = 0  -> ".notdef"
    #   gid 1 -> 1+1+(+1) = 3  -> "space"
    #   gid 2 -> 2+1+(+1) = 4  -> "exclam"
    body = struct.pack(">bbb", -1, 1, 1)
    blob = _pack_header(2, fmt_frac=0x8000) + body
    t = _read(blob, _StubTTF(num_glyphs=3))
    assert t.get_format_type() == 2.5
    names = t.get_glyph_names()
    assert names == [".notdef", "space", "exclam"]


def test_format_2_5_out_of_range_index_blanks_name() -> None:
    # Only one glyph; offset pushes beyond WGL4 -> empty string in slot
    body = struct.pack(">b", 100)  # gid 0 -> 0+1+100 = 101 (still in range)
    blob = _pack_header(2, fmt_frac=0x8000) + body
    t = _read(blob, _StubTTF(num_glyphs=1))
    names = t.get_glyph_names()
    assert names is not None
    assert len(names) == 1
    # gid0 = 101 -> WGL4 index 101 which is "Eacute"
    assert names[0] == "Eacute"


def test_format_2_5_invalid_index_remains_blank() -> None:
    # offset such that gid 0 -> 0+1+127 = 128 (still valid)
    # Use a second glyph that overflows: gid 1 -> 1+1+127 = 129 (valid)
    # Force one truly invalid: use gid 0 -> 0+1+(-2) = -1 (negative)
    body = struct.pack(">b", -2)
    blob = _pack_header(2, fmt_frac=0x8000) + body
    t = _read(blob, _StubTTF(num_glyphs=1))
    names = t.get_glyph_names()
    # Upstream FontBox leaves the String[] slot null (not ""), so the
    # parity-correct result is [None]. get_name(0) likewise returns None.
    assert names == [None]
    assert t.get_name(0) is None


def test_italic_angle_fractional() -> None:
    # italic angle = -10.5 -> whole = -11, frac = 0x8000
    blob = _pack_header(3, italic_whole=-11, italic_frac=0x8000)
    t = _read(blob)
    assert t.get_italic_angle() == -10.5


def test_set_glyph_names_round_trip() -> None:
    t = PostScriptTable()
    t.set_glyph_names(["A", "B"])
    assert t.get_glyph_names() == ["A", "B"]
    assert t.get_name(0) == "A"
    assert t.get_name(1) == "B"
    assert t.get_name(2) is None
    t.set_glyph_names(None)
    assert t.get_glyph_names() is None
    assert t.get_name(0) is None


def test_scalar_setters_round_trip() -> None:
    t = PostScriptTable()
    t.set_format_type(2.5)
    t.set_italic_angle(-12.25)
    t.set_underline_position(-80)
    t.set_underline_thickness(24)
    t.set_is_fixed_pitch(1)
    t.set_min_mem_type42(10)
    t.set_max_mem_type42(20)
    t.set_min_mem_type1(30)
    t.set_max_mem_type1(40)

    assert t.get_format_type() == 2.5
    assert t.get_italic_angle() == -12.25
    assert t.get_underline_position() == -80
    assert t.get_underline_thickness() == 24
    assert t.get_is_fixed_pitch() == 1
    assert t.get_min_mem_type42() == 10
    assert t.get_max_mem_type42() == 20
    assert t.get_min_mem_type1() == 30
    assert t.get_max_mem_type1() == 40

    t.set_mim_mem_type1(31)
    assert t.get_min_mem_type1() == 31


def test_format_4_synthesizes_a_names_from_cids() -> None:
    # Format 4.0 (CID Mac fonts): per-glyph 16-bit CID. Names are "aN".
    cids = [0, 42, 65535]
    body = b"".join(struct.pack(">H", c) for c in cids)
    blob = _pack_header(4) + body
    t = _read(blob, _StubTTF(num_glyphs=len(cids)))
    assert t.get_format_type() == 4.0
    names = t.get_glyph_names()
    assert names == ["a0", "a42", "a65535"]
    assert t.get_name(1) == "a42"
    assert t.get_initialized() is True


def test_format_4_truncated_keeps_remaining_undefined() -> None:
    # Claim 3 glyphs but only supply 2 CIDs; the third stays as .undefined.
    body = struct.pack(">HH", 7, 8)
    blob = _pack_header(4) + body
    t = _read(blob, _StubTTF(num_glyphs=3))
    names = t.get_glyph_names()
    assert names == ["a7", "a8", ".undefined"]


def test_format_3_with_extra_bytes_does_not_create_names() -> None:
    blob = _pack_header(3) + b"\x00\x00\x00"
    t = _read(blob)
    assert t.get_format_type() == 3.0
    assert t.get_glyph_names() is None


def test_initial_state_before_read() -> None:
    t = PostScriptTable()
    assert t.get_format_type() == 0.0
    assert t.get_italic_angle() == 0.0
    assert t.get_underline_position() == 0
    assert t.get_underline_thickness() == 0
    assert t.get_is_fixed_pitch() == 0
    assert t.get_min_mem_type42() == 0
    assert t.get_max_mem_type42() == 0
    assert t.get_min_mem_type1() == 0
    assert t.get_max_mem_type1() == 0
    assert t.get_glyph_names() is None
    assert t.get_name(0) is None
    assert t.get_initialized() is False


def test_table_tag_constant() -> None:
    assert PostScriptTable.TAG == "post"


def test_format_1_only_header_warns_and_skips_names() -> None:
    # When the parser reaches end-of-stream right after the header it logs a
    # warning and does NOT populate glyph_names, regardless of format.
    blob = _pack_header(1)
    t = _read(blob)
    assert t.get_format_type() == 1.0
    assert t.get_glyph_names() is None


def test_format_2_empty_table_zero_glyphs() -> None:
    body = struct.pack(">H", 0)
    blob = _pack_header(2) + body
    t = _read(blob)
    assert t.get_format_type() == 2.0
    assert t.get_glyph_names() == []


def test_format_2_truncated_index_table_raises() -> None:
    # Claim 5 glyphs but supply only one index — the parser should raise an
    # OSError/EOFError from the underlying stream.
    import pytest as _pytest

    body = struct.pack(">HH", 5, 0)
    blob = _pack_header(2) + body
    with _pytest.raises((OSError, EOFError)):
        _read(blob)


def test_has_glyph_names_default_is_false() -> None:
    t = PostScriptTable()
    assert t.has_glyph_names() is False


def test_has_glyph_names_format_1() -> None:
    # Format 1 populates the WGL4 standard list.
    blob = _pack_header(1) + b"\x00"  # any trailing byte to escape EOF guard
    t = _read(blob)
    assert t.get_format_type() == 1.0
    assert t.has_glyph_names() is True
    assert len(t.get_glyph_names() or []) > 0


def test_has_glyph_names_format_3_is_false() -> None:
    # Format 3 carries no glyph names.
    blob = _pack_header(3) + b"\x00\x00\x00"
    t = _read(blob)
    assert t.has_glyph_names() is False


def test_has_glyph_names_empty_format_2() -> None:
    # An explicit format-2 table with zero glyphs creates [] which is not None
    # but also has no names — the predicate reports False.
    body = struct.pack(">H", 0)
    blob = _pack_header(2) + body
    t = _read(blob)
    assert t.get_glyph_names() == []
    assert t.has_glyph_names() is False


def test_is_fixed_pitch_predicate_default() -> None:
    t = PostScriptTable()
    assert t.is_fixed_pitch() is False


def test_is_fixed_pitch_predicate_when_zero() -> None:
    blob = _pack_header(3, is_fixed_pitch=0)
    t = _read(blob)
    assert t.get_is_fixed_pitch() == 0
    assert t.is_fixed_pitch() is False


def test_is_fixed_pitch_predicate_when_set() -> None:
    blob = _pack_header(3, is_fixed_pitch=1)
    t = _read(blob)
    assert t.get_is_fixed_pitch() == 1
    assert t.is_fixed_pitch() is True


def test_is_fixed_pitch_any_nonzero_value() -> None:
    # The on-disk field is 32-bit; any non-zero value indicates fixed pitch.
    blob = _pack_header(3, is_fixed_pitch=0xDEADBEEF)
    t = _read(blob)
    assert t.is_fixed_pitch() is True
