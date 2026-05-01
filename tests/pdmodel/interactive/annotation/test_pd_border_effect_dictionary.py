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
