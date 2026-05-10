from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationPolygon,
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)

# ---------- /IC (interior color) — both subtypes ----------


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_interior_color_default_is_none(cls) -> None:
    assert cls().get_interior_color() is None


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_interior_color_round_trip_three_components(cls) -> None:
    ann = cls()
    ann.set_interior_color((0.25, 0.5, 0.75))
    assert ann.get_interior_color() == (0.25, 0.5, 0.75)


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_interior_color_round_trip_writes_three_floats(cls) -> None:
    ann = cls()
    # Use exactly-representable binary fractions to avoid float32 noise.
    ann.set_interior_color([0.125, 0.25, 0.5])
    raw = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("IC"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 3
    assert raw.to_float_array() == [0.125, 0.25, 0.5]


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_interior_color_set_none_removes_entry(cls) -> None:
    ann = cls()
    ann.set_interior_color((0.0, 0.0, 0.0))
    ann.set_interior_color(None)
    assert ann.get_interior_color() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("IC"))


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_interior_color_short_array_returns_none(cls) -> None:
    ann = cls()
    ann.get_cos_object().set_item(
        COSName.get_pdf_name("IC"),
        COSArray([COSFloat(0.5), COSFloat(0.5)]),
    )
    assert ann.get_interior_color() is None


# ---------- /BS (border style) — both subtypes ----------


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_border_style_default_is_none(cls) -> None:
    assert cls().get_border_style() is None


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_border_style_round_trip_typed(cls) -> None:
    ann = cls()
    bs = PDBorderStyleDictionary()
    bs.set_width(2.5)
    bs.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    ann.set_border_style(bs)
    fetched = ann.get_border_style()
    assert fetched is not None
    assert fetched.get_width() == 2.5
    assert fetched.get_style() == "D"
    # Same underlying COSDictionary instance.
    assert fetched.get_cos_object() is bs.get_cos_object()


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_border_style_round_trip_raw_dict(cls) -> None:
    ann = cls()
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("S"), "S")
    ann.set_border_style(raw)
    fetched = ann.get_border_style()
    assert fetched is not None
    assert fetched.get_cos_object() is raw


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_border_style_set_none_removes_entry(cls) -> None:
    ann = cls()
    ann.set_border_style(PDBorderStyleDictionary())
    ann.set_border_style(None)
    assert ann.get_border_style() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("BS"))


# ---------- /BE (border effect) — both subtypes ----------


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_border_effect_default_is_none(cls) -> None:
    assert cls().get_border_effect() is None


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_border_effect_round_trip(cls) -> None:
    ann = cls()
    be = COSDictionary()
    be.set_name(COSName.get_pdf_name("S"), "C")
    be.set_float(COSName.get_pdf_name("I"), 1.5)
    ann.set_border_effect(be)
    fetched = ann.get_border_effect()
    assert fetched is not None
    # Typed wrapper around the same underlying COSDictionary.
    assert fetched.get_cos_object() is be
    assert fetched.get_style() == "C"
    assert fetched.get_intensity() == 1.5


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_border_effect_set_none_removes_entry(cls) -> None:
    ann = cls()
    ann.set_border_effect(COSDictionary())
    ann.set_border_effect(None)
    assert ann.get_border_effect() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("BE"))


# ---------- /IT (intent) — both subtypes (inherited from markup) ----------


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_intent_default_is_none(cls) -> None:
    assert cls().get_intent() is None


def test_polygon_intent_round_trip() -> None:
    ann = PDAnnotationPolygon()
    ann.set_intent("PolygonCloud")
    assert ann.get_intent() == "PolygonCloud"


def test_polyline_intent_round_trip() -> None:
    ann = PDAnnotationPolyline()
    ann.set_intent("PolyLineDimension")
    assert ann.get_intent() == "PolyLineDimension"


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_intent_set_none_removes_entry(cls) -> None:
    ann = cls()
    ann.set_intent("PolygonCloud")
    ann.set_intent(None)
    assert ann.get_intent() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("IT"))


# ---------- /Measure — both subtypes ----------


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_measure_default_is_none(cls) -> None:
    assert cls().get_measure() is None


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_measure_round_trip(cls) -> None:
    from pypdfbox.pdmodel.interactive.measurement import PDMeasureDictionary

    ann = cls()
    measure = COSDictionary()
    measure.set_name(COSName.TYPE, "Measure")  # type: ignore[attr-defined]
    measure.set_name(COSName.get_pdf_name("Subtype"), "RL")
    ann.set_measure(measure)
    fetched = ann.get_measure()
    assert isinstance(fetched, PDMeasureDictionary)
    # Same underlying COSDictionary instance.
    assert fetched.get_cos_object() is measure


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_measure_set_none_removes_entry(cls) -> None:
    ann = cls()
    ann.set_measure(COSDictionary())
    ann.set_measure(None)
    assert ann.get_measure() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("Measure"))


# ---------- /LE (line ending styles) — polyline only ----------


def test_polyline_line_ending_styles_default_is_none() -> None:
    assert PDAnnotationPolyline().get_line_ending_styles() is None


def test_polyline_line_ending_styles_round_trip() -> None:
    ann = PDAnnotationPolyline()
    ann.set_line_ending_styles("OpenArrow", "ClosedArrow")
    assert ann.get_line_ending_styles() == ("OpenArrow", "ClosedArrow")


def test_polyline_line_ending_styles_overwrites_existing() -> None:
    ann = PDAnnotationPolyline()
    ann.set_line_ending_styles("None", "None")
    ann.set_line_ending_styles("Square", "Diamond")
    assert ann.get_line_ending_styles() == ("Square", "Diamond")


def test_polyline_line_ending_styles_persisted_as_name_array() -> None:
    ann = PDAnnotationPolyline()
    ann.set_line_ending_styles("OpenArrow", "Butt")
    raw = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("LE"))
    assert isinstance(raw, COSArray)
    assert raw.size() == 2
    first = raw.get(0)
    second = raw.get(1)
    assert isinstance(first, COSName) and first.name == "OpenArrow"
    assert isinstance(second, COSName) and second.name == "Butt"


def test_polyline_line_ending_styles_short_array_returns_none() -> None:
    ann = PDAnnotationPolyline()
    ann.get_cos_object().set_item(
        COSName.get_pdf_name("LE"),
        COSArray([COSName.get_pdf_name("OpenArrow")]),
    )
    assert ann.get_line_ending_styles() is None


# ---------- Polygon does not expose /LE accessors ----------


def test_polygon_has_no_line_ending_styles_accessor() -> None:
    # Polygon (closed shape) has no /LE per PDF 32000-1 Table 174.
    assert not hasattr(PDAnnotationPolygon, "get_line_ending_styles")
    assert not hasattr(PDAnnotationPolygon, "set_line_ending_styles")
