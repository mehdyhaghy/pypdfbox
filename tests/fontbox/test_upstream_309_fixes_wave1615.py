"""Regression tests for PDFBox 3.0.9 fontbox fixes that pypdfbox already
matched: PDFBOX-6325 (CMap usecmap one-byte reverse map), PDFBOX-6327
(CMapStrings null on any other length), PDFBOX-6326 (TrueTypeFont.nameToGID
without a Unicode cmap) and PDFBOX-6335 (TTFSubsetter OS/2 version)."""

import io
from pathlib import Path

import pytest
from fontTools import ttLib

from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_strings import CMapStrings
from pypdfbox.fontbox.ttf import TrueTypeFont, TTFSubsetter

_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def test_pdfbox6325_use_cmap_keeps_one_byte_code_0xff() -> None:
    # upstream used ``k % 0xFF``, which mapped 0xFF to 0x00
    parent = CMap("parent")
    parent.add_char_mapping(b"\xff", "y")
    parent.add_char_mapping(b"\x41", "A")
    child = CMap("child")
    child.use_cmap(parent)
    assert child.get_codes_from_unicode("y") == b"\xff"
    assert child.get_codes_from_unicode("A") == b"\x41"


@pytest.mark.parametrize(
    "data", [b"", b"\x00\x00\x00", b"\x00\x00\x00\x00\x00"], ids=["0", "3", "5"]
)
def test_pdfbox6327_cmap_strings_other_lengths_return_none(data: bytes) -> None:
    assert CMapStrings.get_mapping(data) is None


def _font_without_cmap() -> TrueTypeFont:
    if not _FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {_FIXTURE}")
    tt = ttLib.TTFont(io.BytesIO(_FIXTURE.read_bytes()))
    del tt["cmap"]
    # no glyph names, so ``uniXXXX`` reaches the cmap branch
    tt["post"].formatType = 3.0
    buf = io.BytesIO()
    tt.save(buf)
    return TrueTypeFont.from_bytes(buf.getvalue())


def test_pdfbox6326_name_to_gid_without_unicode_cmap() -> None:
    font = _font_without_cmap()
    assert font.get_unicode_cmap_lookup(is_strict=False) is None
    assert font.name_to_gid("uni0041") == 0
    # falls through to the PDFBOX-5604 ``gNNN`` branch
    assert font.name_to_gid("g5") == 5


# Table sizes per OS/2 version (OpenType spec).
_OS2_SIZES = {0: 78, 1: 86, 2: 96, 3: 96, 4: 96, 5: 100}


def test_pdfbox6335_subset_os2_version_matches_written_fields() -> None:
    # Upstream wrote only the version 0 fields but copied the source version
    # number. fontTools writes every field of the version it records.
    if not _FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {_FIXTURE}")
    font = TrueTypeFont.from_bytes(_FIXTURE.read_bytes())
    subsetter = TTFSubsetter(font)
    subsetter.add(ord("a"))
    out = io.BytesIO()
    subsetter.write_to_stream(out)
    tt = ttLib.TTFont(io.BytesIO(out.getvalue()))
    version = tt["OS/2"].version
    assert len(tt.reader["OS/2"]) == _OS2_SIZES[version]
