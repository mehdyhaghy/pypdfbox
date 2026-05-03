from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_caret import (
    PDAnnotationCaret,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_highlight import (
    PDAnnotationHighlight,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
    PDAnnotationInk,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polygon import (
    PDAnnotationPolygon,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_polyline import (
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_popup import (
    PDAnnotationPopup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_squiggly import (
    PDAnnotationSquiggly,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_strikeout import (
    PDAnnotationStrikeout,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_text_markup import (
    PDAnnotationTextMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_underline import (
    PDAnnotationUnderline,
)

# ---------- subtype constants — note non-trivial caps ----------

def test_highlight_subtype() -> None:
    assert PDAnnotationHighlight.SUB_TYPE == "Highlight"
    assert PDAnnotationHighlight().get_subtype() == "Highlight"


def test_underline_subtype() -> None:
    assert PDAnnotationUnderline.SUB_TYPE == "Underline"
    assert PDAnnotationUnderline().get_subtype() == "Underline"


def test_strikeout_subtype_caps() -> None:
    # Spec: StrikeOut, not Strikeout
    assert PDAnnotationStrikeout.SUB_TYPE == "StrikeOut"
    assert PDAnnotationStrikeout().get_subtype() == "StrikeOut"


def test_squiggly_subtype() -> None:
    assert PDAnnotationSquiggly.SUB_TYPE == "Squiggly"
    assert PDAnnotationSquiggly().get_subtype() == "Squiggly"


def test_caret_subtype() -> None:
    assert PDAnnotationCaret.SUB_TYPE == "Caret"
    assert PDAnnotationCaret().get_subtype() == "Caret"


def test_ink_subtype() -> None:
    assert PDAnnotationInk.SUB_TYPE == "Ink"
    assert PDAnnotationInk().get_subtype() == "Ink"


def test_polygon_subtype() -> None:
    assert PDAnnotationPolygon.SUB_TYPE == "Polygon"
    assert PDAnnotationPolygon().get_subtype() == "Polygon"


def test_polyline_subtype_caps() -> None:
    # Spec: PolyLine, not Polyline
    assert PDAnnotationPolyline.SUB_TYPE == "PolyLine"
    assert PDAnnotationPolyline().get_subtype() == "PolyLine"


# ---------- PDAnnotationMarkup base round-trips ----------


def test_markup_subject_round_trip() -> None:
    ann = PDAnnotationCaret()
    assert ann.get_subject() is None
    ann.set_subject("Review note")
    assert ann.get_subject() == "Review note"


def test_markup_constant_opacity_default_is_one() -> None:
    ann = PDAnnotationCaret()
    assert ann.get_constant_opacity() == 1.0


def test_markup_constant_opacity_round_trip() -> None:
    ann = PDAnnotationCaret()
    ann.set_constant_opacity(0.5)
    assert ann.get_constant_opacity() == 0.5


def test_markup_in_reply_to_round_trip() -> None:
    ann = PDAnnotationCaret()
    other = COSDictionary()
    ann.set_in_reply_to(other)
    assert ann.get_in_reply_to() is other


def test_markup_in_reply_to_clear() -> None:
    ann = PDAnnotationCaret()
    ann.set_in_reply_to(COSDictionary())
    ann.set_in_reply_to(None)
    assert ann.get_in_reply_to() is None


def test_markup_popup_round_trip_with_typed_wrapper() -> None:
    ann = PDAnnotationCaret()
    popup = PDAnnotationPopup()
    popup.set_open(True)

    ann.set_popup(popup)

    got = ann.get_popup()
    assert isinstance(got, PDAnnotationPopup)
    assert got.get_cos_object() is popup.get_cos_object()
    assert got.get_open() is True


def test_markup_popup_accepts_raw_dictionary_and_clear() -> None:
    ann = PDAnnotationCaret()
    popup_dict = COSDictionary()
    ann.set_popup(popup_dict)

    got = ann.get_popup()
    assert isinstance(got, PDAnnotationPopup)
    assert got.get_cos_object() is popup_dict

    ann.set_popup(None)
    assert ann.get_popup() is None


def test_markup_reply_type_round_trip() -> None:
    ann = PDAnnotationCaret()
    ann.set_reply_type(PDAnnotationMarkup.RT_GROUP)
    assert ann.get_reply_type() == "Group"
    ann.set_reply_type(PDAnnotationMarkup.RT_REPLY)
    assert ann.get_reply_type() == "R"


def test_markup_intent_round_trip() -> None:
    ann = PDAnnotationCaret()
    ann.set_intent("FreeTextCallout")
    assert ann.get_intent() == "FreeTextCallout"


def test_markup_creation_date_round_trip() -> None:
    ann = PDAnnotationCaret()
    ann.set_creation_date("D:20260426120000Z00'00'")
    assert ann.get_creation_date() == "D:20260426120000Z00'00'"


def test_markup_rich_contents_round_trip_and_clear() -> None:
    ann = PDAnnotationCaret()
    ann.set_rich_contents("<body><p>Reviewed</p></body>")
    assert ann.get_rich_contents() == "<body><p>Reviewed</p></body>"

    ann.set_rich_contents(None)
    assert ann.get_rich_contents() is None


def test_markup_external_data_round_trip_and_clear() -> None:
    ann = PDAnnotationCaret()
    ex_data = COSDictionary()

    ann.set_external_data(ex_data)

    assert ann.get_external_data() is ex_data

    ann.set_external_data(None)
    assert ann.get_external_data() is None


def test_markup_external_data_ignores_non_dictionary_value() -> None:
    ann = PDAnnotationCaret()
    ann.get_cos_object().set_string("ExData", "not a dictionary")

    assert ann.get_external_data() is None


# ---------- PDAnnotationTextMarkup (via Highlight) ----------


def test_text_markup_quad_points_round_trip() -> None:
    ann = PDAnnotationHighlight()
    assert isinstance(ann, PDAnnotationTextMarkup)
    qp = [0.0, 0.0, 10.0, 0.0, 10.0, 10.0, 0.0, 10.0]
    ann.set_quad_points(qp)
    rt = ann.get_quad_points()
    assert rt == qp


def test_text_markup_quad_points_default_empty() -> None:
    """Upstream ``PDAnnotationTextMarkup(String subType)`` ctor seeds
    ``/QuadPoints`` with an empty array; default-constructed Python
    instances mirror that, so the entry is present and round-trips as
    an empty list rather than absent (None)."""
    ann = PDAnnotationHighlight()
    assert ann.get_quad_points() == []


def test_text_markup_quad_points_clear() -> None:
    ann = PDAnnotationHighlight()
    ann.set_quad_points([0.0, 0.0, 1.0, 1.0, 2.0, 2.0, 3.0, 3.0])
    ann.set_quad_points(None)
    assert ann.get_quad_points() is None


def test_text_markup_quad_points_empty_array_round_trip() -> None:
    """Upstream constructor seeds ``setQuadPoints(new float[0])`` — an
    empty array round-trips as an empty list (not null), distinct from a
    missing entry."""
    ann = PDAnnotationHighlight()
    ann.set_quad_points([])
    assert ann.get_quad_points() == []


def test_text_markup_quad_points_works_for_all_subtypes() -> None:
    qp = [0.0, 0.0, 10.0, 0.0, 10.0, 10.0, 0.0, 10.0]
    for cls in (
        PDAnnotationHighlight,
        PDAnnotationUnderline,
        PDAnnotationStrikeout,
        PDAnnotationSquiggly,
    ):
        ann = cls()
        ann.set_quad_points(qp)
        assert ann.get_quad_points() == qp


def test_text_markup_subtypes_share_common_base() -> None:
    for cls in (
        PDAnnotationHighlight,
        PDAnnotationUnderline,
        PDAnnotationStrikeout,
        PDAnnotationSquiggly,
    ):
        assert issubclass(cls, PDAnnotationTextMarkup)
        assert isinstance(cls(), PDAnnotationTextMarkup)


# ---------- Ink ----------


def test_ink_list_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.annotation import PDInkList

    ann = PDAnnotationInk()
    inner = COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(5.0), COSFloat(5.0)])
    outer = COSArray([inner])
    ann.set_ink_list(outer)
    rt = ann.get_ink_list()
    assert isinstance(rt, PDInkList)
    assert rt.get_cos_array() is outer


def test_ink_list_default_none() -> None:
    ann = PDAnnotationInk()
    assert ann.get_ink_list() is None


def test_ink_list_clear() -> None:
    ann = PDAnnotationInk()
    ann.set_ink_list(COSArray([COSArray()]))
    ann.set_ink_list(None)
    assert ann.get_ink_list() is None


# ---------- Polygon ----------


def test_polygon_vertices_round_trip() -> None:
    ann = PDAnnotationPolygon()
    v = [0.0, 0.0, 10.0, 0.0, 10.0, 10.0]
    ann.set_vertices(v)
    assert ann.get_vertices() == v


def test_polygon_vertices_default_none() -> None:
    ann = PDAnnotationPolygon()
    assert ann.get_vertices() is None


def test_polyline_vertices_round_trip() -> None:
    ann = PDAnnotationPolyline()
    v = [0.0, 0.0, 5.0, 5.0]
    ann.set_vertices(v)
    assert ann.get_vertices() == v


# ---------- Wave 237: PDAnnotationMarkup gap fills ----------


# /RT default is RT_REPLY ("R"), not None — upstream uses
# getNameAsString(COSName.RT, RT_REPLY).
def test_markup_reply_type_default_is_reply() -> None:
    ann = PDAnnotationCaret()
    assert ann.get_reply_type() == PDAnnotationMarkup.RT_REPLY
    assert ann.get_reply_type() == "R"


def test_markup_reply_type_clear_resets_to_default() -> None:
    ann = PDAnnotationCaret()
    ann.set_reply_type(PDAnnotationMarkup.RT_GROUP)
    assert ann.get_reply_type() == "Group"

    ann.set_reply_type(None)
    # /RT removed → default "R" comes back, not None.
    assert ann.get_reply_type() == "R"
    assert "RT" not in ann.get_cos_object()


# /RC supports COSStream bodies upstream — toTextString-style decode.
def test_markup_rich_contents_round_trip_with_cos_string() -> None:
    ann = PDAnnotationCaret()
    ann.get_cos_object().set_item(
        COSName.get_pdf_name("RC"), COSString("<body><p>via cos string</p></body>")
    )
    assert ann.get_rich_contents() == "<body><p>via cos string</p></body>"


def test_markup_rich_contents_round_trip_with_cos_stream() -> None:
    ann = PDAnnotationCaret()
    stream = COSStream()
    payload = "<body><p>via cos stream</p></body>"
    with stream.create_raw_output_stream() as out:
        # PDFDocEncoded body → COSString.get_string decodes round-trip.
        out.write(payload.encode("ascii"))
    ann.get_cos_object().set_item(COSName.get_pdf_name("RC"), stream)

    assert ann.get_rich_contents() == payload


def test_markup_rich_contents_returns_none_for_unexpected_type() -> None:
    ann = PDAnnotationCaret()
    # Stash a name where /RC is expected — neither COSString nor COSStream.
    ann.get_cos_object().set_item(
        COSName.get_pdf_name("RC"), COSName.get_pdf_name("Bogus")
    )
    assert ann.get_rich_contents() is None


def test_markup_set_rich_contents_clear_removes_entry() -> None:
    ann = PDAnnotationCaret()
    ann.set_rich_contents("<p>x</p>")
    assert ann.get_rich_contents() == "<p>x</p>"

    ann.set_rich_contents(None)
    assert ann.get_rich_contents() is None
    assert "RC" not in ann.get_cos_object()


# /BS round trips on markup-rooted annotations (upstream defines accessors
# directly on PDAnnotationMarkup).
def test_markup_border_style_default_none() -> None:
    ann = PDAnnotationCaret()
    assert ann.get_border_style() is None


def test_markup_border_style_round_trip_with_typed_wrapper() -> None:
    ann = PDAnnotationCaret()
    bs = PDBorderStyleDictionary()
    bs.set_width(2.5)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)

    ann.set_border_style(bs)

    got = ann.get_border_style()
    assert isinstance(got, PDBorderStyleDictionary)
    assert got.get_cos_object() is bs.get_cos_object()
    assert got.get_width() == 2.5
    assert got.get_style() == PDBorderStyleDictionary.STYLE_DASHED


def test_markup_border_style_accepts_raw_dictionary() -> None:
    ann = PDAnnotationCaret()
    raw = COSDictionary()
    raw.set_float(COSName.get_pdf_name("W"), 1.25)
    ann.set_border_style(raw)

    got = ann.get_border_style()
    assert isinstance(got, PDBorderStyleDictionary)
    assert got.get_cos_object() is raw


def test_markup_border_style_clear_removes_entry() -> None:
    ann = PDAnnotationCaret()
    ann.set_border_style(PDBorderStyleDictionary())
    ann.set_border_style(None)

    assert ann.get_border_style() is None
    assert "BS" not in ann.get_cos_object()


def test_markup_border_style_ignores_non_dictionary_value() -> None:
    ann = PDAnnotationCaret()
    ann.get_cos_object().set_string("BS", "not a dict")
    assert ann.get_border_style() is None


# Predicate helper — has_popup
def test_markup_has_popup_default_false() -> None:
    ann = PDAnnotationCaret()
    assert ann.has_popup() is False


def test_markup_has_popup_true_when_set() -> None:
    ann = PDAnnotationCaret()
    ann.set_popup(COSDictionary())
    assert ann.has_popup() is True


def test_markup_has_popup_false_when_cleared() -> None:
    ann = PDAnnotationCaret()
    ann.set_popup(COSDictionary())
    ann.set_popup(None)
    assert ann.has_popup() is False


def test_markup_has_popup_false_for_non_dictionary_value() -> None:
    ann = PDAnnotationCaret()
    ann.get_cos_object().set_string("Popup", "not a dict")
    assert ann.has_popup() is False
