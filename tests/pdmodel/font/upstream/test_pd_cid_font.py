"""Behaviour parity tests for ``PDCIDFont``.

Apache PDFBox does not ship a dedicated ``PDCIDFontTest.java`` — the
abstract base is exercised only indirectly through the
``PDCIDFontType0`` / ``PDCIDFontType2`` test files. This module ports
the documented behaviour of ``PDCIDFont`` itself: the constructor's
``readWidths`` + ``readVerticalDisplacements`` pre-pass, the ``/DW`` /
``/DW2`` defaults, the ``getDefaultPositionVector`` formula
(``widthForCID(cid)/2, dw2[0]``), the ``getAverageFontWidth``
fall-back to ``/DW``, and the ``readCIDToGIDMap`` big-endian word
parser.

Each test references the originating upstream source line so future
re-syncs against ``pdfbox.git`` are diffable.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSStream
from pypdfbox.pdmodel.font.pd_cid_font import PDCIDFont
from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2

# ---------- /DW default + /DW fallback (PDCIDFont.java line 247) ----------


def test_default_width_is_1000_when_dw_absent() -> None:
    # Upstream PDCIDFont.getDefaultWidth() returns 1000 when /DW is not
    # present on the dictionary (PDCIDFont.java line 257).
    font = PDCIDFontType2()
    assert font.get_default_width() == 1000.0


def test_default_width_reads_dw_when_present() -> None:
    font = PDCIDFontType2()
    font.set_dw(750)
    assert font.get_default_width() == 750.0


# ---------- /W parsing (PDCIDFont.java line 81 readWidths) ----------


def test_read_widths_form_one_consecutive_array() -> None:
    # Form 1: ``c [w1 w2 w3]`` — consecutive CIDs starting at c.
    # PDCIDFont.java lines 99-117.
    font = PDCIDFontType2()
    w = COSArray(
        [
            COSInteger.get(10),
            COSArray([COSInteger.get(100), COSInteger.get(200), COSInteger.get(300)]),
        ]
    )
    font.set_w(w)
    widths = font.read_widths()
    assert widths == {10: 100.0, 11: 200.0, 12: 300.0}


def test_read_widths_form_two_range() -> None:
    # Form 2: ``c1 c2 w`` — every CID in c1..c2 gets the same width.
    # PDCIDFont.java lines 119-141.
    font = PDCIDFontType2()
    w = COSArray(
        [COSInteger.get(5), COSInteger.get(8), COSInteger.get(500)]
    )
    font.set_w(w)
    widths = font.read_widths()
    assert widths == {5: 500.0, 6: 500.0, 7: 500.0, 8: 500.0}


def test_read_widths_mixed_forms() -> None:
    font = PDCIDFontType2()
    w = COSArray(
        [
            COSInteger.get(0),
            COSArray([COSInteger.get(111), COSInteger.get(222)]),
            COSInteger.get(10),
            COSInteger.get(11),
            COSInteger.get(333),
        ]
    )
    font.set_w(w)
    widths = font.read_widths()
    assert widths == {0: 111.0, 1: 222.0, 10: 333.0, 11: 333.0}


def test_read_widths_returns_empty_when_w_missing() -> None:
    assert PDCIDFontType2().read_widths() == {}


# ---------- get_width_for_cid mirrors getWidthForCID (line 274) ----------


def test_get_width_for_cid_falls_back_to_default_width() -> None:
    # PDCIDFont.java lines 274-282: getWidthForCID returns DW when the
    # CID is absent from the parsed /W table.
    font = PDCIDFontType2()
    font.set_dw(444)
    font.set_w(COSArray([COSInteger.get(0), COSArray([COSInteger.get(100)])]))
    assert font.get_width_for_cid(0) == 100.0
    assert font.get_width_for_cid(99) == 444.0


# ---------- /DW2 defaults (PDCIDFont.java line 63 dw2 = [880,-1000]) ----------


def test_dw2_defaults_to_880_minus_1000() -> None:
    # Upstream initialises dw2 = new float[]{880, -1000} on the field
    # declaration (PDCIDFont.java line 63). Surfacing absence via the
    # default-position-vector helpers must yield those values.
    font = PDCIDFontType2()
    assert font.get_default_position_vector() == (880.0, -1000.0)
    assert font.get_dw2_position_vector_y() == 880.0
    assert font.get_dw2_displacement_vector_y() == -1000.0


def test_dw2_round_trip_overrides_defaults() -> None:
    font = PDCIDFontType2()
    font.set_dw2(COSArray([COSInteger.get(700), COSInteger.get(-900)]))
    assert font.get_default_position_vector() == (700.0, -900.0)


# ---------- /W2 parsing (PDCIDFont.java line 146 readVerticalDisplacements) ----


def test_read_vertical_displacements_form_one() -> None:
    # Form 1: ``c [w1y v_x v_y w1y v_x v_y ...]`` — PDCIDFont.java lines
    # 169-181.
    font = PDCIDFontType2()
    w2 = COSArray(
        [
            COSInteger.get(7),
            COSArray(
                [
                    COSInteger.get(-1000),
                    COSInteger.get(500),
                    COSInteger.get(880),
                    COSInteger.get(-1100),
                    COSInteger.get(550),
                    COSInteger.get(870),
                ]
            ),
        ]
    )
    font.set_w2(w2)
    displacements = font.read_vertical_displacements()
    assert displacements[7] == (-1000.0, 500.0, 880.0)
    assert displacements[8] == (-1100.0, 550.0, 870.0)


def test_read_vertical_displacements_form_two_range() -> None:
    # Form 2: ``c1 c2 w1y v_x v_y`` (PDCIDFont.java lines 183-191).
    font = PDCIDFontType2()
    w2 = COSArray(
        [
            COSInteger.get(0),
            COSInteger.get(2),
            COSInteger.get(-880),
            COSInteger.get(400),
            COSInteger.get(880),
        ]
    )
    font.set_w2(w2)
    font.read_vertical_displacements()
    triple = font._get_w2_metrics(1)
    assert triple == (-880.0, 400.0, 880.0)


# ---------- getDefaultPositionVector (PDCIDFont.java line 269) ----------


def test_get_default_position_vector_for_cid_uses_half_width_and_dw2_y() -> None:
    # Upstream returns ``new Vector(getWidthForCID(cid)/2, dw2[0])``
    # (PDCIDFont.java line 271). Without /W2 coverage,
    # get_position_vector falls through to this formula.
    font = PDCIDFontType2()
    font.set_dw(1000)
    # /DW2 defaults to (880, -1000); half-width is 500.
    assert font.get_position_vector(7) == (500.0, 880.0)


# ---------- getAverageFontWidth (PDCIDFont.java line 350) ----------


def test_average_font_width_falls_back_to_dw_when_widths_empty() -> None:
    # Upstream falls back to getDefaultWidth() when /W is empty or no
    # entry contributes a positive width (PDCIDFont.java lines 366-374).
    font = PDCIDFontType2()
    font.set_dw(321)
    assert font.get_average_font_width() == 321.0


def test_average_font_width_means_positive_widths_only() -> None:
    # PDCIDFont.java lines 357-365: only positive widths contribute to
    # the average; 0-width glyphs are skipped.
    font = PDCIDFontType2()
    font.set_w(
        COSArray(
            [
                COSInteger.get(0),
                COSArray(
                    [
                        COSInteger.get(0),  # skipped
                        COSInteger.get(100),
                        COSInteger.get(300),
                    ]
                ),
            ]
        )
    )
    assert font.get_average_font_width() == 200.0


# ---------- readCIDToGIDMap (PDCIDFont.java line 421) ----------


def test_read_cid_to_gid_map_decodes_big_endian_words() -> None:
    # PDCIDFont.java lines 432-438: 16-bit big-endian unsigned GIDs.
    font = PDCIDFontType2()
    stream = COSStream()
    stream.set_data(b"\x00\x00\x00\x2a\x01\x00\xff\xff")
    font.set_cid_to_gid_map(stream)
    result = font.read_cid_to_gid_map()
    assert result == [0, 42, 256, 0xFFFF]


def test_read_cid_to_gid_map_returns_none_when_absent() -> None:
    assert PDCIDFontType2().read_cid_to_gid_map() is None


def test_read_cid_to_gid_map_returns_none_for_identity_name() -> None:
    # Upstream getCOSStream returns null for the /Identity name
    # (PDCIDFont.java line 424); readCIDToGIDMap returns null.
    font = PDCIDFontType2()
    font.set_cid_to_gid_map("Identity")
    assert font.read_cid_to_gid_map() is None


# ---------- has_explicit_width (PDCIDFont.java line 285) ----------


def test_has_explicit_width_true_only_when_w_covers_cid() -> None:
    font = PDCIDFontType2()
    font.set_w(COSArray([COSInteger.get(5), COSArray([COSInteger.get(700)])]))
    assert font.has_explicit_width(5) is True
    # /DW=1000 covers other CIDs but has_explicit_width must still be
    # False — it only reports /W coverage (PDCIDFont.java line 287).
    assert font.has_explicit_width(99) is False


# ---------- abstract method guards (PDCIDFont.java lines 396-419) ----------


def test_code_to_gid_is_abstract_on_bare_pd_cid_font() -> None:
    # Upstream PDCIDFont.codeToGID is declared ``abstract`` (line 405).
    base = PDCIDFont(COSDictionary())
    with pytest.raises(NotImplementedError):
        base.code_to_gid(0)


def test_encode_glyph_id_is_abstract_on_bare_pd_cid_font() -> None:
    # Upstream PDCIDFont.encodeGlyphId is declared ``abstract``
    # (line 407).
    base = PDCIDFont(COSDictionary())
    with pytest.raises(NotImplementedError):
        base.encode_glyph_id(0)


def test_encode_is_abstract_on_bare_pd_cid_font() -> None:
    # Upstream PDCIDFont.encode is declared ``protected abstract``
    # (line 419).
    base = PDCIDFont(COSDictionary())
    with pytest.raises(NotImplementedError):
        base.encode(0x41)
