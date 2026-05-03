"""Parity tests for ``PDMeasureDictionary`` subtype constants and predicate
helpers.

PDF 32000-1 §12.7.5.5 / §12.7.5.6 define two ``/Subtype`` values for
measure dictionaries: ``"RL"`` (rectlinear) and ``"GEO"`` (geospatial).
Upstream PDFBox 3.0.x exposes only ``PDRectlinearMeasureDictionary.SUBTYPE``
("RL"); pypdfbox additionally exposes the constants on the base class
plus :meth:`PDMeasureDictionary.is_rectlinear` /
:meth:`PDMeasureDictionary.is_geospatial` predicates so callers can
dispatch on the subtype string without importing the subclass.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.measurement import (
    PDMeasureDictionary,
    PDRectlinearMeasureDictionary,
)

_SUBTYPE = COSName.SUBTYPE  # type: ignore[attr-defined]


# ---------- subtype constants ----------


def test_subtype_rectlinear_constant_value() -> None:
    assert PDMeasureDictionary.SUBTYPE_RECTLINEAR == "RL"


def test_subtype_geospatial_constant_value() -> None:
    assert PDMeasureDictionary.SUBTYPE_GEOSPATIAL == "GEO"


def test_subtype_rectlinear_matches_subclass_constant() -> None:
    # Base-class constant must agree with the subclass's own SUBTYPE so
    # callers can use either spelling interchangeably.
    assert (
        PDMeasureDictionary.SUBTYPE_RECTLINEAR
        == PDRectlinearMeasureDictionary.SUBTYPE
    )


def test_subtype_constants_inherited_by_subclass() -> None:
    # Subclasses inherit the constants — useful for callers that have a
    # PDRectlinearMeasureDictionary handle and want the GEO sibling.
    assert PDRectlinearMeasureDictionary.SUBTYPE_RECTLINEAR == "RL"
    assert PDRectlinearMeasureDictionary.SUBTYPE_GEOSPATIAL == "GEO"


# ---------- is_rectlinear ----------


def test_is_rectlinear_true_when_absent_subtype_defaults_to_rl() -> None:
    # get_subtype() defaults to "RL" when /Subtype is missing — predicate
    # therefore reports True for a freshly-constructed (no-subtype)
    # PDMeasureDictionary, mirroring upstream's "RL is the default".
    md = PDMeasureDictionary()
    assert md.is_rectlinear() is True


def test_is_rectlinear_true_when_subtype_is_rl_name() -> None:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "RL")
    md = PDMeasureDictionary(raw)
    assert md.is_rectlinear() is True


def test_is_rectlinear_true_for_rectlinear_subclass_default() -> None:
    rl = PDRectlinearMeasureDictionary()
    assert rl.is_rectlinear() is True


def test_is_rectlinear_false_when_subtype_is_geo() -> None:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "GEO")
    md = PDMeasureDictionary(raw)
    assert md.is_rectlinear() is False


def test_is_rectlinear_handles_cos_string_storage() -> None:
    # /Subtype stored as a COSString (rather than a COSName) is still
    # surfaced via get_subtype() — predicate respects that lenience.
    raw = COSDictionary()
    raw.set_item(_SUBTYPE, COSString("RL"))
    md = PDMeasureDictionary(raw)
    assert md.is_rectlinear() is True


def test_is_rectlinear_false_for_unknown_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "XYZ")
    md = PDMeasureDictionary(raw)
    assert md.is_rectlinear() is False


# ---------- is_geospatial ----------


def test_is_geospatial_true_when_subtype_is_geo_name() -> None:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "GEO")
    md = PDMeasureDictionary(raw)
    assert md.is_geospatial() is True


def test_is_geospatial_handles_cos_string_storage() -> None:
    raw = COSDictionary()
    raw.set_item(_SUBTYPE, COSString("GEO"))
    md = PDMeasureDictionary(raw)
    assert md.is_geospatial() is True


def test_is_geospatial_false_when_absent_subtype() -> None:
    # Absent /Subtype defaults to "RL", not "GEO".
    md = PDMeasureDictionary()
    assert md.is_geospatial() is False


def test_is_geospatial_false_for_rectlinear_default() -> None:
    rl = PDRectlinearMeasureDictionary()
    assert rl.is_geospatial() is False


def test_is_geospatial_false_for_unknown_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "XYZ")
    md = PDMeasureDictionary(raw)
    assert md.is_geospatial() is False


def test_predicates_are_mutually_exclusive_for_known_subtypes() -> None:
    # For the two known subtypes, exactly one predicate fires.
    rl_raw = COSDictionary()
    rl_raw.set_name(_SUBTYPE, "RL")
    rl_md = PDMeasureDictionary(rl_raw)
    assert rl_md.is_rectlinear() != rl_md.is_geospatial()

    geo_raw = COSDictionary()
    geo_raw.set_name(_SUBTYPE, "GEO")
    geo_md = PDMeasureDictionary(geo_raw)
    assert geo_md.is_rectlinear() != geo_md.is_geospatial()


def test_predicates_both_false_for_unknown_subtype() -> None:
    raw = COSDictionary()
    raw.set_name(_SUBTYPE, "XYZ")
    md = PDMeasureDictionary(raw)
    assert md.is_rectlinear() is False
    assert md.is_geospatial() is False


def test_predicate_after_internal_set_subtype() -> None:
    # _set_subtype writes a COSName — predicate must agree.
    md = PDMeasureDictionary()
    md._set_subtype("GEO")
    assert md.is_geospatial() is True
    assert md.is_rectlinear() is False
    md._set_subtype("RL")
    assert md.is_rectlinear() is True
    assert md.is_geospatial() is False
