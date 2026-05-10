"""Upstream-shaped parity tests for ``FDFAnnotationLine``.

Upstream PDFBox does not ship a dedicated ``FDFAnnotationLineTest`` (Line
fixtures live inside ``xfdf-test-document-annotations.xml`` exercised via
``FDFAnnotationTest.loadXFDFAnnotations()``). These tests instead pin the
public-method behaviour line-for-line against ``FDFAnnotationLine.java`` so
future re-syncs notice if upstream diverges.

Java references:
  pdfbox/src/main/java/org/apache/pdfbox/pdmodel/fdf/FDFAnnotationLine.java
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.fdf import FDFAnnotationLine

# ---- ctor ----------------------------------------------------------------

def test_default_ctor_stamps_subtype_line() -> None:
    """Java line 45-48: default constructor sets /Subtype /Line."""
    a = FDFAnnotationLine()
    assert a.get_subtype() == FDFAnnotationLine.SUBTYPE
    assert FDFAnnotationLine.SUBTYPE == "Line"


def test_dictionary_ctor_preserves_dict() -> None:
    """Java line 55-58: dictionary constructor wraps the supplied dict."""
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Line"))
    a = FDFAnnotationLine(d)
    assert a.get_cos_object() is d


# ---- /L line coordinates -------------------------------------------------

def test_set_line_round_trip() -> None:
    """Java line 153-158: setLine writes /L as a float array."""
    a = FDFAnnotationLine()
    a.set_line([1.0, 2.0, 3.0, 4.0])
    assert a.get_line() == [1.0, 2.0, 3.0, 4.0]


def test_get_line_returns_none_when_absent() -> None:
    """Java line 165-169: getLine returns null when /L is missing."""
    a = FDFAnnotationLine()
    assert a.get_line() is None


# ---- /LE line ending styles ---------------------------------------------

def test_default_start_point_ending_style_is_none() -> None:
    """Java line 198-202: default start ending is LE_NONE when /LE absent."""
    a = FDFAnnotationLine()
    assert a.get_start_point_ending_style() == "None"


def test_default_end_point_ending_style_is_none() -> None:
    """Java line 231-235: default end ending is LE_NONE when /LE absent."""
    a = FDFAnnotationLine()
    assert a.get_end_point_ending_style() == "None"


def test_set_start_point_ending_style_creates_le_with_none_tail() -> None:
    """Java line 176-191: setStartPointEndingStyle pads tail entry with None."""
    a = FDFAnnotationLine()
    a.set_start_point_ending_style("OpenArrow")
    assert a.get_start_point_ending_style() == "OpenArrow"
    assert a.get_end_point_ending_style() == "None"


def test_set_end_point_ending_style_creates_le_with_none_head() -> None:
    """Java line 209-224: setEndPointEndingStyle pads head entry with None."""
    a = FDFAnnotationLine()
    a.set_end_point_ending_style("ClosedArrow")
    assert a.get_start_point_ending_style() == "None"
    assert a.get_end_point_ending_style() == "ClosedArrow"


def test_set_start_point_ending_style_updates_existing_le() -> None:
    """Java line 187-190: existing /LE is mutated in place."""
    a = FDFAnnotationLine()
    a.set_end_point_ending_style("Diamond")
    a.set_start_point_ending_style("Square")
    assert a.get_start_point_ending_style() == "Square"
    assert a.get_end_point_ending_style() == "Diamond"


# ---- /IC interior colour -------------------------------------------------

def test_set_interior_color_writes_three_floats() -> None:
    """Java line 242-252: setInteriorColor stores RGB float array."""
    a = FDFAnnotationLine()
    a.set_interior_color((0.25, 0.5, 0.75))
    assert a.get_interior_color() == (0.25, 0.5, 0.75)


def test_set_interior_color_none_clears_entry() -> None:
    """Java line 244-251: passing null array clears /IC."""
    a = FDFAnnotationLine()
    a.set_interior_color((0.1, 0.2, 0.3))
    a.set_interior_color(None)
    assert a.get_interior_color() is None


# ---- /Cap caption flag ---------------------------------------------------

def test_caption_default_false() -> None:
    """Java line 279-282: getCaption defaults to false when /Cap absent."""
    a = FDFAnnotationLine()
    assert a.get_caption() is False


def test_set_caption_round_trip() -> None:
    """Java line 269-272: setCaption writes /Cap boolean."""
    a = FDFAnnotationLine()
    a.set_caption(True)
    assert a.get_caption() is True


# ---- /LL /LLE /LLO leader entries ---------------------------------------

def test_leader_length_round_trip() -> None:
    """Java line 289-302: /LL leader length getter/setter."""
    a = FDFAnnotationLine()
    assert a.get_leader_length() == 0.0
    a.set_leader_length(7.5)
    assert a.get_leader_length() == 7.5


def test_leader_extend_round_trip() -> None:
    """Java line 309-322: /LLE leader extension getter/setter."""
    a = FDFAnnotationLine()
    assert a.get_leader_extend() == 0.0
    a.set_leader_extend(2.25)
    assert a.get_leader_extend() == 2.25


def test_leader_offset_round_trip() -> None:
    """Java line 329-342: /LLO leader offset getter/setter."""
    a = FDFAnnotationLine()
    assert a.get_leader_offset() == 0.0
    a.set_leader_offset(-1.5)
    assert a.get_leader_offset() == -1.5


# ---- /CP caption style ---------------------------------------------------

def test_caption_style_default_none() -> None:
    """Java line 349-352: getCaptionStyle returns null when /CP absent."""
    a = FDFAnnotationLine()
    assert a.get_caption_style() is None


def test_caption_style_round_trip_inline() -> None:
    """Java line 359-362: /CP allowed value 'Inline'."""
    a = FDFAnnotationLine()
    a.set_caption_style("Inline")
    assert a.get_caption_style() == "Inline"


def test_caption_style_round_trip_top() -> None:
    """Java line 359-362: /CP allowed value 'Top'."""
    a = FDFAnnotationLine()
    a.set_caption_style("Top")
    assert a.get_caption_style() == "Top"


# ---- /CO caption offsets -------------------------------------------------

def test_caption_horizontal_offset_default_zero() -> None:
    """Java line 389-393: caption horizontal offset defaults to 0.0."""
    a = FDFAnnotationLine()
    assert a.get_caption_horizontal_offset() == 0.0


def test_caption_vertical_offset_default_zero() -> None:
    """Java line 420-424: caption vertical offset defaults to 0.0."""
    a = FDFAnnotationLine()
    assert a.get_caption_vertical_offset() == 0.0


def test_set_caption_horizontal_offset_creates_co_with_zero_v() -> None:
    """Java line 369-382: setCaptionHorizontalOffset seeds [h, 0]."""
    a = FDFAnnotationLine()
    a.set_caption_horizontal_offset(3.0)
    assert a.get_caption_horizontal_offset() == 3.0
    assert a.get_caption_vertical_offset() == 0.0


def test_set_caption_vertical_offset_creates_co_with_zero_h() -> None:
    """Java line 400-413: setCaptionVerticalOffset seeds [0, v]."""
    a = FDFAnnotationLine()
    a.set_caption_vertical_offset(4.5)
    assert a.get_caption_horizontal_offset() == 0.0
    assert a.get_caption_vertical_offset() == 4.5


def test_set_caption_horizontal_offset_updates_existing_co() -> None:
    """Java line 379-381: existing /CO[0] is replaced in place."""
    a = FDFAnnotationLine()
    a.set_caption_vertical_offset(2.0)
    a.set_caption_horizontal_offset(1.0)
    assert a.get_caption_horizontal_offset() == 1.0
    assert a.get_caption_vertical_offset() == 2.0


def test_set_caption_vertical_offset_updates_existing_co() -> None:
    """Java line 410-412: existing /CO[1] is replaced in place."""
    a = FDFAnnotationLine()
    a.set_caption_horizontal_offset(1.0)
    a.set_caption_vertical_offset(2.0)
    assert a.get_caption_horizontal_offset() == 1.0
    assert a.get_caption_vertical_offset() == 2.0


def test_caption_offset_reads_existing_array() -> None:
    """Java line 391-393 / 422-424: getter pulls from existing /CO array."""
    d = COSDictionary()
    d.set_item(
        COSName.get_pdf_name("CO"),
        COSArray([COSFloat(1.5), COSFloat(-2.5)]),
    )
    a = FDFAnnotationLine(d)
    assert a.get_caption_horizontal_offset() == 1.5
    assert a.get_caption_vertical_offset() == -2.5
