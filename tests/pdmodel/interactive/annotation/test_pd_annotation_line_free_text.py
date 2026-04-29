from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)

# ---------- PDAnnotationLine ----------


def test_line_subtype_constant() -> None:
    assert PDAnnotationLine.SUB_TYPE == "Line"


def test_line_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationLine()
    assert ann.get_subtype() == "Line"


def test_line_set_get_round_trip() -> None:
    ann = PDAnnotationLine()
    ann.set_line([0.0, 0.0, 100.0, 100.0])
    assert ann.get_line() == [0.0, 0.0, 100.0, 100.0]


def test_line_endings_default_none() -> None:
    ann = PDAnnotationLine()
    assert ann.get_start_point_ending_style() == PDAnnotationLine.LE_NONE
    assert ann.get_end_point_ending_style() == PDAnnotationLine.LE_NONE


def test_line_endings_round_trip() -> None:
    ann = PDAnnotationLine()
    ann.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    ann.set_end_point_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)
    assert ann.get_start_point_ending_style() == "OpenArrow"
    assert ann.get_end_point_ending_style() == "ClosedArrow"


def test_line_caption_round_trip() -> None:
    ann = PDAnnotationLine()
    assert ann.get_caption() is False
    ann.set_caption(True)
    assert ann.get_caption() is True


def test_line_caption_offsets_round_trip() -> None:
    ann = PDAnnotationLine()
    ann.set_caption_horizontal_offset(3.5)
    ann.set_caption_vertical_offset(-2.25)
    assert ann.get_caption_horizontal_offset() == 3.5
    assert ann.get_caption_vertical_offset() == -2.25


def test_line_leader_line_length_round_trip() -> None:
    ann = PDAnnotationLine()
    ann.set_leader_line_length(12.5)
    assert ann.get_leader_line_length() == 12.5


def test_line_leader_line_extension_length_round_trip() -> None:
    ann = PDAnnotationLine()
    ann.set_leader_line_extension_length(4.0)
    assert ann.get_leader_line_extension_length() == 4.0


def test_line_ending_constants_match_spec() -> None:
    expected = {
        "LE_NONE": "None",
        "LE_SQUARE": "Square",
        "LE_CIRCLE": "Circle",
        "LE_DIAMOND": "Diamond",
        "LE_OPEN_ARROW": "OpenArrow",
        "LE_CLOSED_ARROW": "ClosedArrow",
        "LE_BUTT": "Butt",
        "LE_R_OPEN_ARROW": "ROpenArrow",
        "LE_R_CLOSED_ARROW": "RClosedArrow",
        "LE_SLASH": "Slash",
    }
    for attr, value in expected.items():
        assert getattr(PDAnnotationLine, attr) == value


# ---------- PDAnnotationFreeText ----------


def test_free_text_subtype_constant() -> None:
    assert PDAnnotationFreeText.SUB_TYPE == "FreeText"


def test_free_text_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_subtype() == "FreeText"


def test_free_text_default_appearance_round_trip() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_default_appearance() is None
    ann.set_default_appearance("/Helv 12 Tf 0 g")
    assert ann.get_default_appearance() == "/Helv 12 Tf 0 g"
    ann.set_default_appearance(None)
    assert ann.get_default_appearance() is None


def test_free_text_q_default_left() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_q() == PDAnnotationFreeText.JUSTIFICATION_LEFT


def test_free_text_q_round_trip() -> None:
    ann = PDAnnotationFreeText()
    for q in (
        PDAnnotationFreeText.JUSTIFICATION_LEFT,
        PDAnnotationFreeText.JUSTIFICATION_CENTER,
        PDAnnotationFreeText.JUSTIFICATION_RIGHT,
    ):
        ann.set_q(q)
        assert ann.get_q() == q


def test_free_text_default_style_string_round_trip() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_default_style_string() is None
    ann.set_default_style_string("font: 12pt Helvetica")
    assert ann.get_default_style_string() == "font: 12pt Helvetica"


def test_free_text_rich_contents_round_trip() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_rich_contents() is None
    ann.set_rich_contents("<body><p>hello</p></body>")
    assert ann.get_rich_contents() == "<body><p>hello</p></body>"


def test_free_text_intent_round_trip() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_intent() is None
    ann.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    assert ann.get_intent() == "FreeTextCallout"
    ann.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_TYPE_WRITER)
    assert ann.get_intent() == "FreeTextTypeWriter"
    ann.set_intent(None)
    assert ann.get_intent() is None


def test_free_text_justification_constants() -> None:
    assert PDAnnotationFreeText.JUSTIFICATION_LEFT == 0
    assert PDAnnotationFreeText.JUSTIFICATION_CENTER == 1
    assert PDAnnotationFreeText.JUSTIFICATION_RIGHT == 2


def test_free_text_intent_constants() -> None:
    assert PDAnnotationFreeText.IT_FREE_TEXT == "FreeText"
    assert PDAnnotationFreeText.IT_FREE_TEXT_PLAIN == "FreeText"
    assert PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT == "FreeTextCallout"
    assert PDAnnotationFreeText.IT_FREE_TEXT_TYPE_WRITER == "FreeTextTypeWriter"


def test_free_text_callout_line_default_none() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_callout_line() is None


def test_free_text_callout_line_round_trip_4_floats() -> None:
    ann = PDAnnotationFreeText()
    ann.set_callout_line([10.0, 20.0, 30.0, 40.0])
    assert ann.get_callout_line() == [10.0, 20.0, 30.0, 40.0]


def test_free_text_callout_line_round_trip_6_floats() -> None:
    ann = PDAnnotationFreeText()
    ann.set_callout_line([10.0, 20.0, 30.0, 40.0, 50.0, 60.0])
    assert ann.get_callout_line() == [10.0, 20.0, 30.0, 40.0, 50.0, 60.0]


def test_free_text_callout_alias_matches_callout_line() -> None:
    ann = PDAnnotationFreeText()
    ann.set_callout([1.0, 2.0, 3.0, 4.0])

    assert ann.get_callout() == [1.0, 2.0, 3.0, 4.0]
    assert ann.get_callout_line() == [1.0, 2.0, 3.0, 4.0]


def test_free_text_callout_line_clear() -> None:
    ann = PDAnnotationFreeText()
    ann.set_callout_line([1.0, 2.0, 3.0, 4.0])
    ann.set_callout_line(None)
    assert ann.get_callout_line() is None


def test_free_text_line_ending_default_none() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_line_ending() == PDAnnotationLine.LE_NONE


def test_free_text_line_ending_round_trip() -> None:
    ann = PDAnnotationFreeText()
    ann.set_line_ending(PDAnnotationLine.LE_OPEN_ARROW)
    assert ann.get_line_ending() == "OpenArrow"


def test_free_text_line_ending_style_alias_matches_line_ending() -> None:
    ann = PDAnnotationFreeText()
    ann.set_line_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)

    assert ann.get_line_ending_style() == "ClosedArrow"
    assert ann.get_line_ending() == "ClosedArrow"


def test_free_text_border_style_default_none() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_border_style() is None


def test_free_text_border_style_round_trip() -> None:
    ann = PDAnnotationFreeText()
    bs = PDBorderStyleDictionary()
    bs.set_width(2.0)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    ann.set_border_style(bs)
    fetched = ann.get_border_style()
    assert fetched is not None
    assert fetched.get_width() == 2.0
    assert fetched.get_style() == PDBorderStyleDictionary.STYLE_DASHED
    ann.set_border_style(None)
    assert ann.get_border_style() is None


def test_free_text_border_effect_default_none() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_border_effect() is None


def test_free_text_border_effect_round_trip() -> None:
    ann = PDAnnotationFreeText()
    be = COSDictionary()
    be.set_name(COSName.get_pdf_name("S"), "C")
    be.set_float(COSName.get_pdf_name("I"), 1.5)
    ann.set_border_effect(be)
    fetched = ann.get_border_effect()
    assert fetched is be
    assert fetched.get_name(COSName.get_pdf_name("S")) == "C"
    ann.set_border_effect(None)
    assert ann.get_border_effect() is None


def test_free_text_rectangle_differences_default_none() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_rectangle_differences() is None


def test_free_text_rectangle_differences_round_trip() -> None:
    ann = PDAnnotationFreeText()
    ann.set_rectangle_differences([10.0, 10.0, 10.0, 10.0])
    assert ann.get_rectangle_differences() == [10.0, 10.0, 10.0, 10.0]
    ann.set_rectangle_differences(None)
    assert ann.get_rectangle_differences() is None


def test_free_text_rect_differences_alias_uses_upstream_empty_default() -> None:
    ann = PDAnnotationFreeText()
    assert ann.get_rect_differences() == []
    assert ann.get_rectangle_differences() is None


def test_free_text_rect_differences_alias_accepts_single_difference() -> None:
    ann = PDAnnotationFreeText()
    ann.set_rect_differences(3.5)

    assert ann.get_rect_differences() == [3.5, 3.5, 3.5, 3.5]
    assert ann.get_rectangle_differences() == [3.5, 3.5, 3.5, 3.5]


def test_free_text_rect_differences_alias_accepts_four_differences() -> None:
    ann = PDAnnotationFreeText()
    ann.set_rect_differences(1.0, 2.0, 3.0, 4.0)

    assert ann.get_rect_differences() == [1.0, 2.0, 3.0, 4.0]


def test_free_text_rect_differences_alias_accepts_list_and_clear() -> None:
    ann = PDAnnotationFreeText()
    ann.set_rect_differences([4.0, 3.0, 2.0, 1.0])
    assert ann.get_rect_differences() == [4.0, 3.0, 2.0, 1.0]

    ann.set_rect_differences(None)
    assert ann.get_rect_differences() == []
    assert ann.get_rectangle_differences() is None
