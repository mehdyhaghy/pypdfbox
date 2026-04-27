from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationPolygon,
    PDAnnotationPolyline,
)
from pypdfbox.pdmodel.interactive.measurement import (
    PDMeasureDictionary,
    PDNumberFormatDictionary,
    PDRectlinearMeasureDictionary,
)

_TYPE = COSName.TYPE  # type: ignore[attr-defined]
_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]
_R = COSName.get_pdf_name("R")
_X = COSName.get_pdf_name("X")
_Y = COSName.get_pdf_name("Y")
_D = COSName.get_pdf_name("D")
_A = COSName.get_pdf_name("A")
_T = COSName.get_pdf_name("T")
_S = COSName.get_pdf_name("S")
_O = COSName.get_pdf_name("O")
_CYX = COSName.get_pdf_name("CYX")
_MEASURE = COSName.get_pdf_name("Measure")


# ---------- PDMeasureDictionary ----------


def test_measure_default_constructor_sets_type() -> None:
    md = PDMeasureDictionary()
    cos = md.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert cos.get_name(_TYPE) == "Measure"
    assert md.get_type() == "Measure"


def test_measure_default_constructor_has_no_subtype_yet() -> None:
    md = PDMeasureDictionary()
    # Subtype not stamped — base ctor only sets /Type.
    assert not md.get_cos_object().contains_key(_SUBTYPE)


def test_measure_get_subtype_defaults_to_rl() -> None:
    # Mirrors upstream: getSubtype returns "RL" when /Subtype is absent.
    md = PDMeasureDictionary()
    assert md.get_subtype() == "RL"


def test_measure_get_subtype_returns_existing() -> None:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "GEO")
    md = PDMeasureDictionary(raw)
    assert md.get_subtype() == "GEO"


def test_measure_constructor_with_existing_dictionary_wraps_as_is() -> None:
    raw = COSDictionary()
    md = PDMeasureDictionary(raw)
    assert md.get_cos_object() is raw
    # Wrapping does NOT stamp /Type — matches upstream's COSDictionary ctor.
    assert not raw.contains_key(_TYPE)


def test_measure_set_subtype_writes_name() -> None:
    md = PDMeasureDictionary()
    md._set_subtype("RL")
    assert md.get_cos_object().get_name(_SUBTYPE) == "RL"


# ---------- PDRectlinearMeasureDictionary ----------


def test_rectlinear_default_constructor_sets_type_and_subtype() -> None:
    rl = PDRectlinearMeasureDictionary()
    cos = rl.get_cos_object()
    assert cos.get_name(_TYPE) == "Measure"
    assert cos.get_name(_SUBTYPE) == "RL"
    assert rl.get_type() == "Measure"
    assert rl.get_subtype() == "RL"


def test_rectlinear_constructor_with_existing_dictionary_wraps_as_is() -> None:
    raw = COSDictionary()
    rl = PDRectlinearMeasureDictionary(raw)
    assert rl.get_cos_object() is raw
    # No stamping on wrap — matches upstream PDRectlinearMeasureDictionary(COSDictionary).
    assert not raw.contains_key(_TYPE)
    assert not raw.contains_key(_SUBTYPE)


def test_rectlinear_is_a_pd_measure_dictionary() -> None:
    rl = PDRectlinearMeasureDictionary()
    assert isinstance(rl, PDMeasureDictionary)


def test_rectlinear_scale_ratio_round_trip() -> None:
    rl = PDRectlinearMeasureDictionary()
    assert rl.get_scale_ratio() is None
    rl.set_scale_ratio("1in = 1ft")
    assert rl.get_scale_ratio() == "1in = 1ft"
    assert rl.get_cos_object().get_string(_R) == "1in = 1ft"
    rl.set_scale_ratio(None)
    assert rl.get_scale_ratio() is None
    assert not rl.get_cos_object().contains_key(_R)


@pytest.mark.parametrize(
    ("getter", "setter", "key"),
    [
        ("get_change_xs", "set_change_xs", _X),
        ("get_change_ys", "set_change_ys", _Y),
        ("get_distances", "set_distances", _D),
        ("get_areas", "set_areas", _A),
        ("get_angles", "set_angles", _T),
        ("get_line_sloaps", "set_line_sloaps", _S),
    ],
)
def test_rectlinear_number_format_array_round_trip(
    getter: str, setter: str, key: COSName
) -> None:
    rl = PDRectlinearMeasureDictionary()
    assert getattr(rl, getter)() is None

    nf1 = PDNumberFormatDictionary()
    nf1.set_units("in")
    nf2 = PDNumberFormatDictionary()
    nf2.set_units("ft")

    getattr(rl, setter)([nf1, nf2])
    fetched = getattr(rl, getter)()
    assert fetched is not None
    assert len(fetched) == 2
    # Underlying COSDictionary instances are preserved.
    assert fetched[0].get_cos_object() is nf1.get_cos_object()
    assert fetched[1].get_cos_object() is nf2.get_cos_object()
    # The dictionary entry is a COSArray of NumberFormat dicts.
    raw = rl.get_cos_object().get_dictionary_object(key)
    assert isinstance(raw, COSArray)
    assert raw.size() == 2


def test_rectlinear_number_format_array_overwrites() -> None:
    rl = PDRectlinearMeasureDictionary()
    rl.set_change_xs([PDNumberFormatDictionary()])
    rl.set_change_xs(
        [PDNumberFormatDictionary(), PDNumberFormatDictionary(), PDNumberFormatDictionary()]
    )
    fetched = rl.get_change_xs()
    assert fetched is not None
    assert len(fetched) == 3


def test_rectlinear_number_format_array_accepts_tuple() -> None:
    rl = PDRectlinearMeasureDictionary()
    nf = PDNumberFormatDictionary()
    rl.set_distances((nf,))
    fetched = rl.get_distances()
    assert fetched is not None
    assert len(fetched) == 1


def test_rectlinear_coord_system_origin_round_trip() -> None:
    rl = PDRectlinearMeasureDictionary()
    assert rl.get_coord_system_origin() is None
    rl.set_coord_system_origin([10.5, 20.5])
    assert rl.get_coord_system_origin() == [10.5, 20.5]
    raw = rl.get_cos_object().get_dictionary_object(_O)
    assert isinstance(raw, COSArray)
    assert raw.to_float_array() == [10.5, 20.5]


def test_rectlinear_coord_system_origin_accepts_tuple() -> None:
    rl = PDRectlinearMeasureDictionary()
    rl.set_coord_system_origin((1.0, 2.0))
    assert rl.get_coord_system_origin() == [1.0, 2.0]


def test_rectlinear_cyx_round_trip() -> None:
    rl = PDRectlinearMeasureDictionary()
    # default for absent key in pypdfbox COSDictionary.get_float is -1.0
    assert rl.get_cyx() == -1.0
    rl.set_cyx(1.25)
    assert rl.get_cyx() == pytest.approx(1.25)
    assert rl.get_cos_object().get_float(_CYX) == pytest.approx(1.25)


def test_rectlinear_full_round_trip_via_cos_dictionary() -> None:
    rl = PDRectlinearMeasureDictionary()
    rl.set_scale_ratio("1in = 1mi")
    nf = PDNumberFormatDictionary()
    nf.set_units("mi")
    rl.set_change_xs([nf])
    rl.set_change_ys([nf])
    rl.set_distances([nf])
    rl.set_areas([nf])
    rl.set_angles([nf])
    rl.set_line_sloaps([nf])
    rl.set_coord_system_origin([0.0, 0.0])
    rl.set_cyx(1.0)

    raw = rl.get_cos_object()
    rebuilt = PDRectlinearMeasureDictionary(raw)
    assert rebuilt.get_subtype() == "RL"
    assert rebuilt.get_scale_ratio() == "1in = 1mi"
    assert rebuilt.get_change_xs() is not None
    assert rebuilt.get_change_ys() is not None
    assert rebuilt.get_distances() is not None
    assert rebuilt.get_areas() is not None
    assert rebuilt.get_angles() is not None
    assert rebuilt.get_line_sloaps() is not None
    assert rebuilt.get_coord_system_origin() == [0.0, 0.0]
    assert rebuilt.get_cyx() == pytest.approx(1.0)


# ---------- Polygon / Polyline integration ----------


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_annotation_set_typed_measure_round_trip(cls) -> None:
    ann = cls()
    measure = PDRectlinearMeasureDictionary()
    measure.set_scale_ratio("1cm = 1m")
    ann.set_measure(measure)

    fetched = ann.get_measure()
    assert isinstance(fetched, PDMeasureDictionary)
    # The wrapper points at the same COSDictionary we wrote.
    assert fetched.get_cos_object() is measure.get_cos_object()
    # Re-wrap as the rectlinear subclass to verify the entry survived.
    rebuilt = PDRectlinearMeasureDictionary(fetched.get_cos_object())
    assert rebuilt.get_scale_ratio() == "1cm = 1m"


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_annotation_set_raw_cos_dict_still_supported(cls) -> None:
    ann = cls()
    raw = COSDictionary()
    raw.set_name(_TYPE, "Measure")
    raw.set_name(_SUBTYPE, "RL")
    ann.set_measure(raw)

    fetched = ann.get_measure()
    assert isinstance(fetched, PDMeasureDictionary)
    assert fetched.get_cos_object() is raw


@pytest.mark.parametrize("cls", [PDAnnotationPolygon, PDAnnotationPolyline])
def test_annotation_set_measure_none_removes_entry(cls) -> None:
    ann = cls()
    ann.set_measure(PDRectlinearMeasureDictionary())
    ann.set_measure(None)
    assert ann.get_measure() is None
    assert not ann.get_cos_object().contains_key(_MEASURE)
