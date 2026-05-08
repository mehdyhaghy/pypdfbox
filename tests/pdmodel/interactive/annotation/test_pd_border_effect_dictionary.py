from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)


def test_default_constructor_creates_empty_dict() -> None:
    be = PDBorderEffectDictionary()
    cos = be.get_cos_object()
    assert isinstance(cos, COSDictionary)
    assert len(cos) == 0


def test_constructor_with_dict_preserves_identity() -> None:
    d = COSDictionary()
    be = PDBorderEffectDictionary(d)
    assert be.get_cos_object() is d


def test_default_intensity_is_zero() -> None:
    be = PDBorderEffectDictionary()
    assert be.get_intensity() == 0.0


def test_default_style_is_solid() -> None:
    be = PDBorderEffectDictionary()
    assert be.get_style() == PDBorderEffectDictionary.STYLE_SOLID
    assert be.get_style() == "S"


def test_intensity_round_trip() -> None:
    be = PDBorderEffectDictionary()
    be.set_intensity(1.5)
    assert be.get_intensity() == 1.5
    assert be.get_cos_object().get_float(COSName.get_pdf_name("I")) == 1.5


def test_intensity_zero_round_trip() -> None:
    be = PDBorderEffectDictionary()
    be.set_intensity(0.0)
    assert be.get_intensity() == 0.0


def test_intensity_max_round_trip() -> None:
    be = PDBorderEffectDictionary()
    be.set_intensity(2.0)
    assert be.get_intensity() == 2.0


def test_style_round_trip_cloudy() -> None:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    assert be.get_style() == "C"
    assert be.get_cos_object().get_name(COSName.get_pdf_name("S")) == "C"


def test_style_round_trip_solid() -> None:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_SOLID)
    assert be.get_style() == "S"


def test_set_style_none_clears_entry_and_restores_default() -> None:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    assert be.has_style() is True

    be.set_style(None)

    assert be.has_style() is False
    assert be.get_style() == PDBorderEffectDictionary.STYLE_SOLID
    assert not be.get_cos_object().contains_key(COSName.get_pdf_name("S"))


def test_style_constants() -> None:
    assert PDBorderEffectDictionary.STYLE_SOLID == "S"
    assert PDBorderEffectDictionary.STYLE_CLOUDY == "C"


def test_construct_from_existing_populated_dict() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "C")
    d.set_float(COSName.get_pdf_name("I"), 2.0)
    be = PDBorderEffectDictionary(d)
    assert be.get_style() == "C"
    assert be.get_intensity() == 2.0


def test_re_exported_from_package() -> None:
    from pypdfbox.pdmodel.interactive import annotation

    assert annotation.PDBorderEffectDictionary is PDBorderEffectDictionary


# ---------- Wave 215: predicates, presence detection, and STYLE_VALUES ----------


def test_style_values_constant_is_complete_and_ordered() -> None:
    assert PDBorderEffectDictionary.STYLE_VALUES == ("S", "C")
    # Sanity: the tuple's contents match the named constants.
    assert PDBorderEffectDictionary.STYLE_VALUES[0] == PDBorderEffectDictionary.STYLE_SOLID
    assert PDBorderEffectDictionary.STYLE_VALUES[1] == PDBorderEffectDictionary.STYLE_CLOUDY


def test_style_values_is_tuple_immutable() -> None:
    # Tuple — not a list — so callers cannot mutate the shared constant.
    assert isinstance(PDBorderEffectDictionary.STYLE_VALUES, tuple)


def test_is_solid_default_when_dict_empty() -> None:
    be = PDBorderEffectDictionary()
    assert be.is_solid() is True
    assert be.is_cloudy() is False


def test_is_cloudy_after_set_style_cloudy() -> None:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    assert be.is_cloudy() is True
    assert be.is_solid() is False


def test_is_solid_after_explicit_set_solid() -> None:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_SOLID)
    assert be.is_solid() is True
    assert be.is_cloudy() is False


def test_is_solid_and_is_cloudy_are_mutually_exclusive_for_known_values() -> None:
    for style in PDBorderEffectDictionary.STYLE_VALUES:
        be = PDBorderEffectDictionary()
        be.set_style(style)
        # Exactly one of the two predicates is true for any spec-defined style.
        assert be.is_solid() ^ be.is_cloudy()


def test_unknown_style_is_neither_solid_nor_cloudy() -> None:
    # Spec defines only S and C, but the wire format permits arbitrary names;
    # the predicates must not lie about an unknown value.
    be = PDBorderEffectDictionary()
    be.set_style("X")
    assert be.is_solid() is False
    assert be.is_cloudy() is False
    assert be.get_style() == "X"


def test_has_style_distinguishes_explicit_solid_from_absent() -> None:
    be = PDBorderEffectDictionary()
    assert be.has_style() is False
    be.set_style(PDBorderEffectDictionary.STYLE_SOLID)
    assert be.has_style() is True
    # Both branches still report STYLE_SOLID via get_style — that's the point.
    assert be.get_style() == PDBorderEffectDictionary.STYLE_SOLID


def test_has_intensity_distinguishes_explicit_zero_from_absent() -> None:
    be = PDBorderEffectDictionary()
    assert be.has_intensity() is False
    be.set_intensity(0.0)
    assert be.has_intensity() is True
    # Both branches still report 0.0 via get_intensity — that's the point.
    assert be.get_intensity() == 0.0


def test_has_intensity_after_nonzero_set() -> None:
    be = PDBorderEffectDictionary()
    be.set_intensity(2.0)
    assert be.has_intensity() is True


def test_has_style_after_cloudy_set() -> None:
    be = PDBorderEffectDictionary()
    be.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    assert be.has_style() is True


def test_predicates_on_externally_populated_dict() -> None:
    d = COSDictionary()
    d.set_name(COSName.get_pdf_name("S"), "C")
    d.set_float(COSName.get_pdf_name("I"), 1.5)
    be = PDBorderEffectDictionary(d)
    assert be.is_cloudy() is True
    assert be.is_solid() is False
    assert be.has_style() is True
    assert be.has_intensity() is True


def test_predicates_on_empty_externally_provided_dict() -> None:
    be = PDBorderEffectDictionary(COSDictionary())
    assert be.is_solid() is True
    assert be.is_cloudy() is False
    assert be.has_style() is False
    assert be.has_intensity() is False
