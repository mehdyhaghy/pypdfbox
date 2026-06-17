"""Tests translated from upstream PDFBox.

Upstream sources:
  - pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDType3FontTest.java
  - pdfbox/src/test/java/org/apache/pdfbox/pdmodel/font/PDType3CharProcTest.java
    (upstream baseline 3.0.x)

The upstream JUnit tests centred on parsing real Type 3 PDFs (e.g.
``type3.pdf``, ``PDFBOX-4071-empty-type3.pdf``) — those depend on a
working PDF parser, content-stream tokeniser, and full document open
pipeline that are scoped to later clusters. We translate the remaining
shape/contract tests that exercise the dictionary surface directly,
matching upstream call ordering and assertions one-for-one. Tests
that demand a parser or rendering harness are skipped with a
single-line comment per the project's porting conventions.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.pd_type3_char_proc import PDType3CharProc
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_rectangle import PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources

# ---------- shape: a fresh PDType3Font carries the right /Type and /Subtype ----------


def test_constructor_sets_subtype_to_type3() -> None:
    # Mirrors the implicit upstream check in every PDType3FontTest setup.
    font = PDType3Font()
    assert font.get_subtype() == "Type3"


def test_constructor_sets_type_to_font() -> None:
    font = PDType3Font()
    cos = font.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Font"  # type: ignore[attr-defined]


# ---------- isEmbedded — Type 3 is *always* embedded ----------


def test_is_embedded_true():
    # Mirrors PDType3FontTest pattern: Type 3 fonts have no font program,
    # so isEmbedded() must always return true.
    font = PDType3Font()
    assert font.is_embedded() is True


# ---------- getFontMatrix — default ----------


def test_get_font_matrix_default():
    # Upstream defaults to [0.001, 0, 0, 0.001, 0, 0] per PDF 32000-1 §9.2.4.
    font = PDType3Font()
    assert font.get_font_matrix() == [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]


# ---------- getFontBBox — round-trip through dictionary ----------


def test_get_font_b_box_round_trip():
    font = PDType3Font()
    rect = PDRectangle(0.0, 0.0, 750.0, 1000.0)
    font.set_font_bbox(rect)
    out = font.get_font_bbox()
    assert out is not None
    assert out == rect


# ---------- getResources / setResources ----------


def test_get_resources_round_trip():
    font = PDType3Font()
    resources = PDResources()
    font.set_resources(resources)
    assert font.get_resources() is not None


# ---------- getCharProc / getCharProcs ----------


def test_get_char_procs_initially_none():
    font = PDType3Font()
    assert font.get_char_procs() is None


def test_get_char_proc_returns_typed_wrapper_when_encoded():
    # Mirrors upstream: getCharProc(int code) returns PDType3CharProc.
    font = PDType3Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    char_procs = COSDictionary()
    glyph = COSStream()
    char_procs.set_item(COSName.get_pdf_name("A"), glyph)
    font.set_char_procs(char_procs)

    proc = font.get_char_proc(0x41)
    assert isinstance(proc, PDType3CharProc)
    assert proc.get_font() is font


def test_get_char_proc_returns_none_for_missing_glyph():
    # Upstream returns null when the encoding maps to a name that's not
    # in /CharProcs.
    font = PDType3Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    font.set_char_procs(COSDictionary())  # empty
    assert font.get_char_proc(0x41) is None


# ---------- getWidth(code) ----------


def test_get_width_uses_widths_array():
    # Upstream PDType3Font.getWidth(int) looks up the Widths array offset
    # by /FirstChar; the gate requires both /FirstChar and /LastChar to
    # be set (``code >= firstChar && code <= lastChar``).
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(67)
    font.set_widths([500.0, 600.0, 700.0])
    assert font.get_width(65) == pytest.approx(500.0)
    assert font.get_width(66) == pytest.approx(600.0)
    assert font.get_width(67) == pytest.approx(700.0)


def test_get_width_zero_for_unknown_code():
    font = PDType3Font()
    font.set_first_char(65)
    font.set_last_char(65)
    font.set_widths([500.0])
    # Out of range and no /FontDescriptor -> upstream falls through to
    # getWidthFromFont (no /CharProcs entry -> 0).
    assert font.get_width(100) == 0.0


# ---------- hasGlyph(code) ----------


def test_has_glyph_true_when_encoded_and_present():
    font = PDType3Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name("A"), COSStream())
    font.set_char_procs(char_procs)
    assert font.has_glyph(0x41) is True


def test_has_glyph_false_when_charproc_absent():
    font = PDType3Font()
    font.get_cos_object().set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("WinAnsiEncoding"),
    )
    font.set_char_procs(COSDictionary())
    assert font.has_glyph(0x41) is False


# ---------- PDType3CharProc — d1 bbox parsing ----------


def test_char_proc_get_glyph_bbox_from_d1():
    # Mirrors PDType3CharProcTest: a content stream with leading
    # "wx wy llx lly urx ury d1" exposes its bbox via getGlyphBBox().
    font = PDType3Font()
    glyph = COSStream()
    glyph.set_raw_data(b"600 0 50 -10 550 700 d1\n")
    proc = PDType3CharProc(font, glyph)

    bbox = proc.get_glyph_bbox()
    assert bbox is not None
    assert bbox.get_lower_left_x() == pytest.approx(50.0)
    assert bbox.get_lower_left_y() == pytest.approx(-10.0)
    assert bbox.get_upper_right_x() == pytest.approx(550.0)
    assert bbox.get_upper_right_y() == pytest.approx(700.0)


def test_char_proc_get_glyph_bbox_none_for_d0():
    # d0 declares no bbox -> getGlyphBBox returns null upstream.
    font = PDType3Font()
    glyph = COSStream()
    glyph.set_raw_data(b"600 0 d0\n")
    proc = PDType3CharProc(font, glyph)
    assert proc.get_glyph_bbox() is None


def test_char_proc_get_width_from_d0():
    # The width operand on d0 is the glyph's advance.
    font = PDType3Font()
    glyph = COSStream()
    glyph.set_raw_data(b"600 0 d0\n")
    proc = PDType3CharProc(font, glyph)
    assert proc.get_width() == pytest.approx(600.0)


def test_char_proc_resources_falls_back_to_font():
    # Char-procs without their own /Resources fall back to the font's.
    font = PDType3Font()
    font.set_resources(PDResources())
    glyph = COSStream()
    proc = PDType3CharProc(font, glyph)
    assert proc.get_resources() is not None


def test_char_proc_matrix_delegates_to_font():
    font = PDType3Font()
    font.set_font_matrix([0.002, 0.0, 0.0, 0.002, 0.0, 0.0])
    glyph = COSStream()
    proc = PDType3CharProc(font, glyph)
    matrix = proc.get_matrix()
    assert matrix == pytest.approx([0.002, 0.0, 0.0, 0.002, 0.0, 0.0], rel=1e-6)


# ---------- isDamaged — Type 3 has no font program to load ----------


def test_is_damaged_returns_false():
    # Mirrors upstream PDType3Font.isDamaged() — returns false because
    # there's no font file to load, so no parse step that could fail.
    font = PDType3Font()
    assert font.is_damaged() is False


# ---------- isStandard14 — Type 3 is never one of the Standard 14 ----------


def test_is_standard14_returns_false():
    # Mirrors upstream PDType3Font.isStandard14() — always false even if
    # /BaseFont collides with a Standard 14 name.
    font = PDType3Font()
    assert font.is_standard14() is False


# ---------- generateBoundingBox / checkFontMatrixValues (private upstream) ----------


def test_check_font_matrix_values_six_floats():
    # Mirrors the gating logic in upstream getFontMatrix():
    # checkFontMatrixValues accepts a 6-entry numeric array.
    from pypdfbox.cos import COSArray, COSFloat

    arr = COSArray(
        [
            COSFloat(0.001),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(0.001),
            COSFloat(0.0),
            COSFloat(0.0),
        ]
    )
    assert PDType3Font.check_font_matrix_values(arr) is True


def test_check_font_matrix_values_rejects_short_array():
    from pypdfbox.cos import COSArray, COSFloat

    arr = COSArray([COSFloat(0.001)])
    assert PDType3Font.check_font_matrix_values(arr) is False


def test_generate_bounding_box_no_font_bbox_returns_none():
    # Upstream's generateBoundingBox returns an empty BoundingBox when
    # /FontBBox is missing entirely; pypdfbox surfaces None so callers
    # can distinguish "no bbox" from "explicit zero bbox".
    font = PDType3Font()
    assert font.generate_bounding_box() is None


# Skipped (require parser / open-document pipeline beyond this cluster):
#   - testType3FontWithEmptyCharProc — needs PDFParser + PDDocument.load
#   - testPDFBox4071EmptyType3       — needs PDFParser + content-stream engine
#   - testPDType3CharProcGlyph       — needs PDFRenderer / Glyph2D
