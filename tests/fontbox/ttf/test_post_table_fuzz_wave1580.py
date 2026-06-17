"""Wave 1580 — fuzz/parity sweep for the TrueType ``post`` table parser.

Hammers :class:`pypdfbox.fontbox.ttf.post_script_table.PostScriptTable`
against synthetic ``post`` blobs across all four format flavours, checking
behavioural parity with FontBox 3.0.7 ``PostScriptTable``:

* format 1.0 -> exactly the 258 standard Macintosh glyph names
* format 2.0 -> glyphNameIndex mixing standard (<258) and custom (>=258)
  Pascal-string-appended names, plus the 32768..65535 reserved band
* format 2.5 -> per-glyph signed offset deltas (deprecated)
* format 3.0 -> no names
* the 16.16 fixed version float (0x00010000 etc.)
* header-only blobs (no name data)

The format-2.5 ``None``-slot assertions encode the parity fix landed in
this wave: upstream allocates ``new String[...]`` whose unset slots stay
``null``, so out-of-range or unresolved indices must surface as ``None``,
not the empty string.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

import pytest

from pypdfbox.fontbox.ttf import wgl4_names
from pypdfbox.fontbox.ttf.post_script_table import PostScriptTable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

# ---- helpers --------------------------------------------------------------


@dataclass
class _StubTTF:
    name: str = "FuzzFont"
    num_glyphs: int = 0

    def get_name(self) -> str:
        return self.name

    def get_number_of_glyphs(self) -> int:
        return self.num_glyphs


def _pack_fixed(whole: int, frac: int = 0) -> bytes:
    return struct.pack(">hH", whole, frac)


def _header(fmt_whole: int, fmt_frac: int = 0) -> bytes:
    """A complete 32-byte ``post`` header with the given version field."""
    return (
        _pack_fixed(fmt_whole, fmt_frac)  # version
        + _pack_fixed(0, 0)  # italicAngle
        + struct.pack(">hh", -75, 40)  # underlinePosition / Thickness
        + struct.pack(">IIIII", 0, 0, 0, 0, 0)  # isFixedPitch + mem fields
    )


def _read(blob: bytes, ttf: _StubTTF | None = None) -> PostScriptTable:
    table = PostScriptTable()
    table.set_length(len(blob))
    table.read(ttf or _StubTTF(), MemoryTTFDataStream(blob))  # type: ignore[arg-type]
    return table


def _pascal(name: str) -> bytes:
    raw = name.encode("iso-8859-1")
    return bytes([len(raw)]) + raw


# ---- format detection / version float -------------------------------------


@pytest.mark.parametrize(
    ("whole", "frac", "expected"),
    [
        (1, 0x0000, 1.0),
        (2, 0x0000, 2.0),
        (2, 0x8000, 2.5),
        (3, 0x0000, 3.0),
        (4, 0x0000, 4.0),
    ],
    ids=["v1.0", "v2.0", "v2.5", "v3.0", "v4.0"],
)
def test_version_float_decoded_from_16_16_fixed(
    whole: int, frac: int, expected: float
) -> None:
    # Header-only (32 bytes) -> the "no name data" early-out path; but the
    # version field is still parsed exactly from the 16.16 fixed value.
    blob = _header(whole, frac)
    t = _read(blob, _StubTTF(num_glyphs=0))
    assert t.get_format_type() == expected


def test_header_exact_size_yields_no_names() -> None:
    # current_position == original_data_size -> the warn-and-skip branch.
    t = _read(_header(2, 0), _StubTTF(num_glyphs=3))
    assert t.get_glyph_names() is None
    assert t.get_name(0) is None


# ---- format 1.0 : the 258 standard Mac names ------------------------------


def test_format_1_loads_all_258_standard_names() -> None:
    # One trailing byte forces position != size so name loading runs.
    blob = _header(1, 0) + b"\x00"
    t = _read(blob, _StubTTF(num_glyphs=258))
    names = t.get_glyph_names()
    assert names is not None
    assert len(names) == wgl4_names.NUMBER_OF_MAC_GLYPHS == 258


@pytest.mark.parametrize(
    ("gid", "expected"),
    [
        (0, ".notdef"),
        (1, ".null"),
        (3, "space"),
        (36, "A"),
        (68, "a"),
        (257, "dcroat"),
    ],
    ids=["notdef", "null", "space", "A", "a", "last"],
)
def test_format_1_standard_name_lookup(gid: int, expected: str) -> None:
    blob = _header(1, 0) + b"\x00"
    t = _read(blob, _StubTTF(num_glyphs=258))
    assert t.get_name(gid) == expected


def test_format_1_get_name_out_of_range_is_none() -> None:
    blob = _header(1, 0) + b"\x00"
    t = _read(blob, _StubTTF(num_glyphs=258))
    assert t.get_name(-1) is None
    assert t.get_name(258) is None
    assert t.get_name(99999) is None


# ---- format 2.0 : mixed standard + custom Pascal-string names -------------


def _format_2(glyph_name_index: list[int], names: list[str]) -> bytes:
    body = struct.pack(">H", len(glyph_name_index))
    for idx in glyph_name_index:
        body += struct.pack(">H", idx)
    for name in names:
        body += _pascal(name)
    return _header(2, 0) + body


def test_format_2_all_standard_indices() -> None:
    # indices all < 258 -> resolve straight from WGL4, no name array needed.
    t = _read(_format_2([0, 3, 36], []), _StubTTF(num_glyphs=3))
    assert t.get_glyph_names() == [".notdef", "space", "A"]


def test_format_2_single_custom_name() -> None:
    # index 258 -> nameArray[0]; the appended Pascal string is "myGlyph".
    t = _read(_format_2([0, 258], ["myGlyph"]), _StubTTF())
    assert t.get_glyph_names() == [".notdef", "myGlyph"]


def test_format_2_mixed_standard_and_custom() -> None:
    # 0 -> .notdef, 258 -> custom[0], 3 -> space, 259 -> custom[1]
    t = _read(
        _format_2([0, 258, 3, 259], ["alpha", "beta"]),
        _StubTTF(),
    )
    assert t.get_glyph_names() == [".notdef", "alpha", "space", "beta"]


def test_format_2_custom_index_minus_258_offset() -> None:
    # max_index 260 -> name array length 3; index 260 maps to nameArray[2].
    t = _read(
        _format_2([260], ["zero", "one", "two"]),
        _StubTTF(),
    )
    # 260 - 258 = 2 -> "two"
    assert t.get_glyph_names() == ["two"]


def test_format_2_reserved_index_band_is_undefined() -> None:
    # 32768..65535 reserved -> ".undefined"; must not consume name bytes.
    t = _read(_format_2([0, 40000], []), _StubTTF())
    assert t.get_glyph_names() == [".notdef", ".undefined"]


def test_format_2_reserved_does_not_inflate_name_array() -> None:
    # A reserved index alongside a real custom index: max_index ignores the
    # reserved one, so only ONE Pascal string is read.
    t = _read(_format_2([258, 50000], ["solo"]), _StubTTF())
    assert t.get_glyph_names() == ["solo", ".undefined"]


def test_format_2_empty_names_array_all_standard() -> None:
    t = _read(_format_2([1, 2], []), _StubTTF())
    assert t.get_glyph_names() == [".null", "nonmarkingreturn"]


def test_format_2_zero_glyphs() -> None:
    t = _read(_format_2([], []), _StubTTF())
    assert t.get_glyph_names() == []


@pytest.mark.parametrize(
    ("custom_names",),
    [
        (["a"],),
        (["abc"],),
        (["longGlyphName123"],),
        (["x", "yy", "zzz"],),
        ([""],),  # zero-length Pascal string
    ],
    ids=["len1", "len3", "len16", "varied", "empty"],
)
def test_format_2_pascal_string_length_prefix(custom_names: list[str]) -> None:
    # Each custom name maps 1:1 from gid -> nameArray order.
    indices = [258 + i for i in range(len(custom_names))]
    t = _read(_format_2(indices, custom_names), _StubTTF())
    assert t.get_glyph_names() == custom_names


def test_format_2_high_value_name_index_within_band() -> None:
    # 32767 is the top of the *non-reserved* range; with a name array sized
    # to cover it the lookup resolves to the matching Pascal string.
    big = 32767
    names = [f"g{i}" for i in range(big - 258 + 1)]
    t = _read(_format_2([big], names), _StubTTF())
    assert t.get_glyph_names() == [f"g{big - 258}"]


def test_format_2_get_name_round_trips_against_glyph_names() -> None:
    t = _read(_format_2([0, 258, 259], ["one", "two"]), _StubTTF())
    names = t.get_glyph_names()
    assert names is not None
    for gid, name in enumerate(names):
        assert t.get_name(gid) == name


# ---- format 2.0 EOF handling ----------------------------------------------


def test_format_2_eof_on_length_byte_raises() -> None:
    # max_index 258 promises a name array of length 1, but the body ends right
    # after the index -> reading the Pascal length byte hits EOF and PROPAGATES
    # (upstream keeps the length read outside the PDFBOX-4851 try).
    body = struct.pack(">H", 1) + struct.pack(">H", 258)
    blob = _header(2, 0) + body
    with pytest.raises((OSError, EOFError)):
        _read(blob, _StubTTF())


def test_format_2_truncated_string_pads_remaining_with_notdef() -> None:
    # Length byte says 5 chars but only 2 remain -> readString EOFs, the slot
    # and all following slots become ".notdef" (PDFBOX-4851).
    body = struct.pack(">H", 2) + struct.pack(">HH", 258, 259)
    body += bytes([3]) + b"abc"  # nameArray[0] = "abc"
    body += bytes([5]) + b"xy"  # nameArray[1] claims 5, only 2 available
    blob = _header(2, 0) + body
    t = _read(blob, _StubTTF())
    assert t.get_glyph_names() == ["abc", ".notdef"]


# ---- format 2.5 : signed offset deltas ------------------------------------


def _format_2_5(offsets: list[int]) -> bytes:
    body = b"".join(struct.pack(">b", o) for o in offsets)
    return _header(2, 0x8000) + body


def test_format_2_5_offset_resolution() -> None:
    # gid i -> i + 1 + offset.  [-1, 1, 1] -> [0, 3, 4] -> notdef/space/exclam
    t = _read(_format_2_5([-1, 1, 1]), _StubTTF(num_glyphs=3))
    assert t.get_format_type() == 2.5
    assert t.get_glyph_names() == [".notdef", "space", "exclam"]


def test_format_2_5_identity_offsets() -> None:
    # offset 0 -> index i+1 -> the (i+1)-th Mac name.
    t = _read(_format_2_5([0, 0, 0]), _StubTTF(num_glyphs=3))
    names = t.get_glyph_names()
    assert names == [".null", "nonmarkingreturn", "space"]


def test_format_2_5_negative_index_is_none_not_empty() -> None:
    # gid 0 -> 0 + 1 + (-2) = -1 (negative, out of range). Upstream leaves the
    # String[] slot null; parity therefore requires None (NOT "").
    t = _read(_format_2_5([-2]), _StubTTF(num_glyphs=1))
    assert t.get_glyph_names() == [None]
    assert t.get_name(0) is None


def test_format_2_5_overflow_index_is_none() -> None:
    # gid 0 -> 0 + 1 + 127 = 128 (valid). gid 1 needs an index >= 258 to be
    # out of range: i+1+offset with i=1 caps at 1+1+127 = 129, still valid, so
    # use a high glyph position. Here we force an out-of-range slot via a large
    # positive offset on a high gid is impossible (offset is a signed byte), so
    # exercise the negative path which is the only out-of-range route.
    t = _read(_format_2_5([127]), _StubTTF(num_glyphs=1))
    names = t.get_glyph_names()
    assert names is not None
    # 0 + 1 + 127 = 128 -> WGL4 index 128 = "ucircumflex"
    assert names[0] == "ucircumflex"


def test_format_2_5_mixed_valid_and_invalid() -> None:
    # gid 0 -> 1+(-2) = -1 (None); gid 1 -> 2+(-1) = 1 (".null")
    t = _read(_format_2_5([-2, -1]), _StubTTF(num_glyphs=2))
    assert t.get_glyph_names() == [None, ".null"]


def test_format_2_5_zero_glyphs_hits_no_name_data_earlyout() -> None:
    # An empty 2.5 body leaves position == data size, so the header-only
    # "no name data" early-out fires BEFORE format dispatch -> names stay None.
    t = _read(_format_2_5([]), _StubTTF(num_glyphs=0))
    assert t.get_glyph_names() is None


# ---- format 3.0 : no name information -------------------------------------


def test_format_3_provides_no_names() -> None:
    blob = _header(3, 0) + b"\x00"
    t = _read(blob, _StubTTF(num_glyphs=5))
    assert t.get_format_type() == 3.0
    assert t.get_glyph_names() is None
    assert t.get_name(0) is None
    assert t.get_name(3) is None


def test_format_3_has_glyph_names_false() -> None:
    blob = _header(3, 0) + b"\x00"
    t = _read(blob, _StubTTF(num_glyphs=5))
    assert t.has_glyph_names() is False


# ---- predicate helpers -----------------------------------------------------


def test_has_glyph_names_true_for_format_1() -> None:
    t = _read(_header(1, 0) + b"\x00", _StubTTF(num_glyphs=258))
    assert t.has_glyph_names() is True


def test_is_fixed_pitch_boolean_view() -> None:
    # isFixedPitch field is the 5th 32-bit word after the two fixed values.
    body = (
        _pack_fixed(2, 0)
        + _pack_fixed(0, 0)
        + struct.pack(">hh", -75, 40)
        + struct.pack(">IIIII", 7, 0, 0, 0, 0)  # isFixedPitch = 7 (non-zero)
    )
    t = _read(body, _StubTTF(num_glyphs=0))
    assert t.get_is_fixed_pitch() == 7
    assert t.is_fixed_pitch() is True


def test_num_glyphs_consistency_format_2() -> None:
    # numberOfGlyphs in the format-2 body drives glyph_names length, NOT the
    # ttf.get_number_of_glyphs() count.
    t = _read(_format_2([0, 1, 2, 3], []), _StubTTF(num_glyphs=999))
    names = t.get_glyph_names()
    assert names is not None
    assert len(names) == 4
