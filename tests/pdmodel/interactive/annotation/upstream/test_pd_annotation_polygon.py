"""Upstream-aligned parity tests for ``PDAnnotationPolygon``.

Apache PDFBox 3.0.x has no dedicated ``PDAnnotationPolygonTest.java``;
these tests cover the public API surface of
``org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationPolygon``
(see ``PDAnnotationPolygon.java``) translated to pytest. They lock in
the same defaults, round-trips, and constant catalogue that upstream Java
callers rely on.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationPolygon
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)


def test_subtype_constant_matches_upstream() -> None:
    # PDAnnotationPolygon.java line 36: SUB_TYPE = "Polygon".
    assert PDAnnotationPolygon.SUB_TYPE == "Polygon"


def test_default_constructor_writes_polygon_subtype() -> None:
    # PDAnnotationPolygon.java line 43-46.
    annotation = PDAnnotationPolygon()
    assert annotation.get_subtype() == PDAnnotationPolygon.SUB_TYPE


def test_dict_constructor_keeps_existing_subtype() -> None:
    # PDAnnotationPolygon.java line 53-56.
    backing = COSDictionary()
    backing.set_name(COSName.SUBTYPE, "Polygon")  # type: ignore[attr-defined]
    annotation = PDAnnotationPolygon(backing)
    assert annotation.get_subtype() == "Polygon"
    assert annotation.get_cos_object() is backing


# ---------- /IC interior color ----------


def test_interior_color_default_none() -> None:
    # PDAnnotationPolygon.java line 76-79: returns null when /IC missing.
    assert PDAnnotationPolygon().get_interior_color() is None


def test_interior_color_round_trip() -> None:
    # PDAnnotationPolygon.java line 66-71: /IC is written as a COSArray.
    annotation = PDAnnotationPolygon()
    annotation.set_interior_color((1.0, 0.5, 0.0))
    assert annotation.get_interior_color() == (1.0, 0.5, 0.0)


# ---------- /BE border effect ----------


def test_border_effect_default_none() -> None:
    # PDAnnotationPolygon.java line 96-99: returns null when /BE missing.
    assert PDAnnotationPolygon().get_border_effect() is None


def test_border_effect_round_trip() -> None:
    # PDAnnotationPolygon.java line 88-91 / 96-99: round-trip via the typed
    # PDBorderEffectDictionary wrapper.
    annotation = PDAnnotationPolygon()
    be = PDBorderEffectDictionary()
    annotation.set_border_effect(be)
    fetched = annotation.get_border_effect()
    assert fetched is not None
    assert fetched.get_cos_object() is be.get_cos_object()


# ---------- /Vertices ----------


def test_vertices_default_none() -> None:
    # PDAnnotationPolygon.java line 107-111: returns null when /Vertices
    # is missing.
    assert PDAnnotationPolygon().get_vertices() is None


def test_vertices_round_trip() -> None:
    # PDAnnotationPolygon.java line 119-124.
    annotation = PDAnnotationPolygon()
    annotation.set_vertices([1.0, 2.0, 3.0, 4.0, 5.0, 6.0])
    assert annotation.get_vertices() == [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]


# ---------- /Path (PDF 2.0) ----------


def test_path_default_none() -> None:
    # PDAnnotationPolygon.java line 133-152: returns null when /Path missing.
    assert PDAnnotationPolygon().get_path() is None


def test_path_returns_per_operator_arrays() -> None:
    # PDAnnotationPolygon.java line 133-152: each inner COSArray is mapped
    # to a float list; non-COSArray entries become an empty list.
    annotation = PDAnnotationPolygon()
    backing = annotation.get_cos_object()
    outer = COSArray()
    move_to = COSArray()
    move_to.add(COSFloat(1.0))
    move_to.add(COSFloat(2.0))
    line_to = COSArray()
    line_to.add(COSFloat(3.0))
    line_to.add(COSFloat(4.0))
    curve_to = COSArray()
    for v in (5.0, 6.0, 7.0, 8.0, 9.0, 10.0):
        curve_to.add(COSFloat(v))
    outer.add(move_to)
    outer.add(line_to)
    outer.add(curve_to)
    backing.set_item(COSName.get_pdf_name("Path"), outer)

    path = annotation.get_path()
    assert path == [
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0, 7.0, 8.0, 9.0, 10.0],
    ]


# ---------- appearance handler ----------


def test_construct_appearances_default_is_noop() -> None:
    # PDAnnotationPolygon.java line 167-181: with no custom handler the
    # call delegates to PDPolygonAppearanceHandler. That handler is not
    # ported, so the default path is a no-op via the base class — verified
    # here so a future port doesn't silently change call-site behaviour.
    annotation = PDAnnotationPolygon()
    assert annotation.construct_appearances() is None
    assert annotation.construct_appearances(None) is None


def test_construct_appearances_invokes_custom_handler() -> None:
    # PDAnnotationPolygon.java line 161-181: custom handler delegation.
    annotation = PDAnnotationPolygon()

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
    annotation = PDAnnotationPolygon()

    class _Handler:
        def generate_appearance_streams(self) -> None:
            raise AssertionError("default path expected after clear")

    annotation.set_custom_appearance_handler(_Handler())
    annotation.set_custom_appearance_handler(None)
    assert annotation.get_custom_appearance_handler() is None
    assert annotation.construct_appearances() is None
