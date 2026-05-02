"""Round-out tests for :class:`PDCIDFontType0` (Wave 201).

Covers:
* :meth:`get_font_box_font` — returns the embedded CFF program (or
  ``None`` when not embedded), mirroring upstream
  ``PDCIDFontType0.getFontBoxFont``.
* :meth:`get_type2_char_string` — returns a Type 2 charstring wrapper
  for the given CID (or ``None`` when the font has no embedded
  program), mirroring upstream ``PDCIDFontType0.getType2CharString``.
* :meth:`get_normalized_path` — alias of :meth:`get_glyph_path` for
  CFF-backed CIDFontType0 (no upem scaling needed since CFF expresses
  outlines in 1000 upem by default).
* :meth:`encode_glyph_id` — raises :class:`NotImplementedError`,
  mirroring upstream's ``UnsupportedOperationException``.
"""

from __future__ import annotations

import io

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.fontbox.cff.cff_font import CFFFont
from pypdfbox.pdmodel.font.pd_cid_font_type0 import PDCIDFontType0
from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor

# ---------- fixture helpers ----------


def _build_cid_keyed_cff_bytes() -> bytes:
    """Tiny in-memory CFF font set with ``cidNNNNN`` glyph names —
    matches the byte form a /FontFile3 stream with /Subtype
    /CIDFontType0C carries for CID-keyed CFF programs."""
    from fontTools.fontBuilder import FontBuilder
    from fontTools.misc.psCharStrings import T2CharString
    from fontTools.ttLib import TTFont

    fb = FontBuilder(1000, isTTF=False)
    fb.setupGlyphOrder([".notdef", "cid00001", "cid00002"])
    fb.setupCharacterMap({1: "cid00001", 2: "cid00002"})

    def _cs(program: list) -> T2CharString:
        s = T2CharString()
        s.program = program
        return s

    cs_dict = {
        ".notdef": _cs([0, "endchar"]),
        "cid00001": _cs(
            [500, 0, "hmoveto", 700, "vlineto", 100, "hlineto", -700, "vlineto", "endchar"]
        ),
        "cid00002": _cs([300, 0, "hmoveto", 500, "vlineto", "endchar"]),
    }
    fb.setupCFF(
        psName="TestCIDFontType0C",
        fontInfo={"FullName": "Test CID Font Type0C"},
        charStringsDict=cs_dict,
        privateDict={},
    )
    fb.setupHorizontalMetrics(
        {".notdef": (0, 0), "cid00001": (500, 0), "cid00002": (300, 0)}
    )
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupOS2(sTypoAscender=800, sTypoDescender=-200, usWinAscent=800, usWinDescent=200)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupPost()
    buf = io.BytesIO()
    fb.font.save(buf)
    re_open = TTFont(io.BytesIO(buf.getvalue()))
    return bytes(re_open.getTableData("CFF "))


def _make_embedded_font() -> PDCIDFontType0:
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(_build_cid_keyed_cff_bytes())
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "TestCIDFontType0C")
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDCIDFontType0(font_dict)


# ---------- get_font_box_font ----------


def test_get_font_box_font_none_when_not_embedded() -> None:
    font = PDCIDFontType0()
    assert font.get_font_box_font() is None


def test_get_font_box_font_returns_cff_program_when_embedded() -> None:
    font = _make_embedded_font()
    program = font.get_font_box_font()
    assert isinstance(program, CFFFont)


def test_get_font_box_font_returns_same_object_as_get_cff_font() -> None:
    """``getFontBoxFont`` and ``getCFFFont`` collapse to the same return
    value in our embedding-only port; assert pointer-identity to catch
    accidental divergence."""
    font = _make_embedded_font()
    assert font.get_font_box_font() is font.get_cff_font()


def test_get_font_box_font_caches_via_underlying_cff() -> None:
    font = _make_embedded_font()
    first = font.get_font_box_font()
    second = font.get_font_box_font()
    assert first is second


def test_get_font_box_font_none_after_failed_parse() -> None:
    descriptor = PDFontDescriptor()
    stream = COSStream()
    stream.set_data(b"not a valid CFF font set")
    stream.set_name(COSName.SUBTYPE, "CIDFontType0C")  # type: ignore[attr-defined]
    descriptor.set_font_file3(stream)
    font_dict = COSDictionary()
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDCIDFontType0(font_dict)
    assert font.get_font_box_font() is None


# ---------- get_type2_char_string ----------


def test_get_type2_char_string_none_when_not_embedded() -> None:
    font = PDCIDFontType0()
    assert font.get_type2_char_string(1) is None


def test_get_type2_char_string_returns_wrapper_for_known_cid() -> None:
    font = _make_embedded_font()
    cs = font.get_type2_char_string(1)
    assert cs is not None
    # The wrapper's get_path should return the same outline as
    # get_glyph_path for the same CID.
    path = cs.get_path()
    assert path == font.get_glyph_path(1)


def test_get_type2_char_string_returns_wrapper_for_notdef() -> None:
    font = _make_embedded_font()
    cs = font.get_type2_char_string(0)
    assert cs is not None
    # .notdef in our fixture is a single endchar — empty draw output.
    assert cs.get_path() == []


def test_get_type2_char_string_returns_empty_wrapper_for_unmapped_cid() -> None:
    """Per ``CFFFont.get_type2_char_string`` the out-of-range CID
    yields an empty-program wrapper rather than ``None`` — the upstream
    Java throws but our port deliberately diverges for ergonomics
    (callers probe via ``get_path() == []``).
    """
    font = _make_embedded_font()
    cs = font.get_type2_char_string(9999)
    # Either None (program rejects the lookup outright) or an empty
    # wrapper — either is acceptable; the contract is "no exception".
    if cs is not None:
        assert cs.get_path() == []


# ---------- get_normalized_path ----------


def test_get_normalized_path_empty_when_not_embedded() -> None:
    font = PDCIDFontType0()
    assert font.get_normalized_path(1) == []


def test_get_normalized_path_matches_get_glyph_path() -> None:
    """For CFF-backed CIDFontType0 the normalized path is the raw
    glyph path — no upem scaling needed since CFF expresses outlines
    in 1000 upem by default."""
    font = _make_embedded_font()
    assert font.get_normalized_path(1) == font.get_glyph_path(1)
    assert font.get_normalized_path(2) == font.get_glyph_path(2)


def test_get_normalized_path_empty_for_unmapped_cid() -> None:
    font = _make_embedded_font()
    assert font.get_normalized_path(9999) == []


def test_get_normalized_path_empty_for_notdef_outline() -> None:
    """.notdef is a single ``endchar`` in our fixture — no draw
    commands emitted, so the normalized path is empty too."""
    font = _make_embedded_font()
    assert font.get_normalized_path(0) == []


# ---------- encode_glyph_id (unsupported) ----------


def test_encode_glyph_id_raises_not_implemented() -> None:
    """Mirrors upstream ``PDCIDFontType0.encodeGlyphId`` which throws
    ``UnsupportedOperationException``: encoding by GID is meaningless
    for a CFF-backed CIDFontType0 because GID and CID are distinct
    identities for CID-keyed programs."""
    font = PDCIDFontType0()
    with pytest.raises(NotImplementedError):
        font.encode_glyph_id(1)


def test_encode_glyph_id_raises_even_when_embedded() -> None:
    """The unsupported semantics hold whether or not a font program
    is embedded — upstream's exception is unconditional."""
    font = _make_embedded_font()
    with pytest.raises(NotImplementedError):
        font.encode_glyph_id(0)
    with pytest.raises(NotImplementedError):
        font.encode_glyph_id(0xFFFF)
