from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_border_effect_dictionary import (
    PDBorderEffectDictionary,
)


def test_malformed_border_effect_entries_do_not_report_present() -> None:
    dictionary = COSDictionary()
    dictionary.set_string(COSName.get_pdf_name("S"), "C")
    dictionary.set_name(COSName.get_pdf_name("I"), "High")

    effect = PDBorderEffectDictionary(dictionary)

    # /S is read via getNameAsString upstream, so a COSString value ("C") is
    # decoded by get_style; has_style still checks for a genuine COSName.
    assert effect.get_style() == "C"
    assert effect.get_intensity() == 0.0
    assert effect.has_style() is False
    assert effect.has_intensity() is False


def test_clear_border_effect_entries_restore_defaults() -> None:
    effect = PDBorderEffectDictionary()
    effect.set_style(PDBorderEffectDictionary.STYLE_CLOUDY)
    effect.set_intensity(1.5)

    assert effect.has_style() is True
    assert effect.has_intensity() is True

    effect.clear_style()
    effect.clear_intensity()

    assert effect.get_style() == PDBorderEffectDictionary.STYLE_SOLID
    assert effect.get_intensity() == 0.0
    assert effect.has_style() is False
    assert effect.has_intensity() is False
    assert not effect.get_cos_object().contains_key(COSName.get_pdf_name("S"))
    assert not effect.get_cos_object().contains_key(COSName.get_pdf_name("I"))
