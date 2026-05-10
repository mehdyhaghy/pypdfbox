"""Upstream-aligned parity tests for ``PDAnnotationPolyline``.

Apache PDFBox 3.0.x has no dedicated ``PDAnnotationPolylineTest.java``;
these tests cover the public API surface of
``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolyline``
(see ``PDAnnotationPolyline.java``) translated to pytest. They lock in
the same defaults, round-trips, and constant catalogue that upstream Java
callers rely on.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationPolyline


def test_subtype_constant_matches_upstream() -> None:
    # PDAnnotationPolyline.java line 35: SUB_TYPE = "PolyLine".
    assert PDAnnotationPolyline.SUB_TYPE == "PolyLine"


def test_default_constructor_writes_polyline_subtype() -> None:
    # PDAnnotationPolyline.java line 42-45.
    annotation = PDAnnotationPolyline()
    assert annotation.get_subtype() == PDAnnotationPolyline.SUB_TYPE


def test_dict_constructor_keeps_existing_subtype() -> None:
    # PDAnnotationPolyline.java line 52-55.
    backing = COSDictionary()
    backing.set_name(COSName.SUBTYPE, "PolyLine")  # type: ignore[attr-defined]
    annotation = PDAnnotationPolyline(backing)
    assert annotation.get_subtype() == "PolyLine"
    assert annotation.get_cos_object() is backing


# ---------- /LE start-point ending style ----------


def test_get_start_point_ending_style_default_none() -> None:
    # PDAnnotationPolyline.java line 84-92: returns LE_NONE when /LE missing.
    assert PDAnnotationPolyline().get_start_point_ending_style() == "None"


def test_set_start_point_ending_style_creates_le_array() -> None:
    # PDAnnotationPolyline.java line 62-77: when /LE is missing, a fresh
    # 2-name array is written with the supplied style first and LE_NONE
    # second.
    annotation = PDAnnotationPolyline()
    annotation.set_start_point_ending_style("OpenArrow")
    raw = annotation.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("LE")
    )
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    assert annotation.get_start_point_ending_style() == "OpenArrow"
    assert annotation.get_end_point_ending_style() == "None"


def test_set_start_point_ending_style_overwrites_existing_first_entry() -> None:
    # PDAnnotationPolyline.java line 73-76: when /LE already exists, only
    # index 0 is rewritten — the end style stays put.
    annotation = PDAnnotationPolyline()
    annotation.set_line_ending_styles("ClosedArrow", "Square")
    annotation.set_start_point_ending_style("Diamond")
    assert annotation.get_start_point_ending_style() == "Diamond"
    assert annotation.get_end_point_ending_style() == "Square"


def test_set_start_point_ending_style_none_normalises_to_le_none() -> None:
    # PDAnnotationPolyline.java line 64: ``style == null ? LE_NONE : style``.
    annotation = PDAnnotationPolyline()
    annotation.set_start_point_ending_style(None)
    assert annotation.get_start_point_ending_style() == "None"


# ---------- /LE end-point ending style ----------


def test_get_end_point_ending_style_default_none() -> None:
    # PDAnnotationPolyline.java line 121-129.
    assert PDAnnotationPolyline().get_end_point_ending_style() == "None"


def test_set_end_point_ending_style_creates_le_array() -> None:
    # PDAnnotationPolyline.java line 99-114: when /LE is missing or short,
    # a fresh 2-name array is written with LE_NONE first and the supplied
    # style second.
    annotation = PDAnnotationPolyline()
    annotation.set_end_point_ending_style("ClosedArrow")
    raw = annotation.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("LE")
    )
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    assert annotation.get_start_point_ending_style() == "None"
    assert annotation.get_end_point_ending_style() == "ClosedArrow"


def test_set_end_point_ending_style_overwrites_existing_second_entry() -> None:
    # PDAnnotationPolyline.java line 110-113.
    annotation = PDAnnotationPolyline()
    annotation.set_line_ending_styles("Diamond", "ClosedArrow")
    annotation.set_end_point_ending_style("Butt")
    assert annotation.get_start_point_ending_style() == "Diamond"
    assert annotation.get_end_point_ending_style() == "Butt"


def test_set_end_point_ending_style_none_normalises_to_le_none() -> None:
    # PDAnnotationPolyline.java line 101.
    annotation = PDAnnotationPolyline()
    annotation.set_end_point_ending_style(None)
    assert annotation.get_end_point_ending_style() == "None"


# ---------- /IC interior color (basic round-trip lifted from upstream) ----------


def test_interior_color_round_trip() -> None:
    # PDAnnotationPolyline.java line 136-149.
    annotation = PDAnnotationPolyline()
    annotation.set_interior_color((1.0, 0.5, 0.0))
    assert annotation.get_interior_color() == (1.0, 0.5, 0.0)


# ---------- /Vertices ----------


def test_vertices_default_none() -> None:
    # PDAnnotationPolyline.java line 157-161: returns null when /Vertices
    # is missing.
    assert PDAnnotationPolyline().get_vertices() is None


def test_vertices_round_trip() -> None:
    # PDAnnotationPolyline.java line 170-175.
    annotation = PDAnnotationPolyline()
    annotation.set_vertices([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert annotation.get_vertices() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


# ---------- appearance handler ----------


def test_construct_appearances_default_is_noop() -> None:
    # PDAnnotationPolyline.java line 187-205: with no custom handler the
    # call delegates to PDPolylineAppearanceHandler. That handler is not
    # ported, so the default path is a no-op via the base class — verified
    # here so a future port doesn't silently change call-site behaviour.
    annotation = PDAnnotationPolyline()
    assert annotation.construct_appearances() is None
    assert annotation.construct_appearances(None) is None


def test_construct_appearances_invokes_custom_handler() -> None:
    # PDAnnotationPolyline.java line 182-205: custom handler delegation.
    annotation = PDAnnotationPolyline()

    class _RecordingHandler:
        def __init__(self) -> None:
            self.called = 0

        def generate_appearance_streams(self) -> None:
            self.called += 1

    handler = _RecordingHandler()
    annotation.set_custom_appearance_handler(handler)
    assert annotation.get_custom_appearance_handler() is handler

    annotation.construct_appearances()
    assert handler.called == 1
    annotation.construct_appearances(None)
    assert handler.called == 2


def test_clearing_custom_handler_restores_default_path() -> None:
    annotation = PDAnnotationPolyline()

    class _Handler:
        def generate_appearance_streams(self) -> None:
            raise AssertionError("default path expected after clear")

    annotation.set_custom_appearance_handler(_Handler())
    annotation.set_custom_appearance_handler(None)
    assert annotation.get_custom_appearance_handler() is None
    assert annotation.construct_appearances() is None
