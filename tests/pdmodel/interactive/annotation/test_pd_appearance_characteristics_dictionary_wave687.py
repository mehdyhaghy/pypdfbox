from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)


class _BadColour:
    def to_cos_array(self) -> COSName:
        return COSName.get_pdf_name("NotAnArray")


def test_wave687_rejects_colour_values_that_cannot_be_coerced() -> None:
    mk = PDAppearanceCharacteristicsDictionary()

    with pytest.raises(TypeError, match="colour must be"):
        mk.set_border_colour(object())
    with pytest.raises(TypeError, match="colour must be"):
        mk.set_background(_BadColour())


def test_wave687_raw_colour_array_getters_ignore_non_arrays() -> None:
    dictionary = COSDictionary()
    dictionary.set_item("BC", COSName.get_pdf_name("NotAnArray"))
    dictionary.set_item("BG", COSName.get_pdf_name("NotAnArray"))
    mk = PDAppearanceCharacteristicsDictionary(dictionary)

    assert mk.get_border_colour_array() is None
    assert mk.get_background_array() is None


def test_wave687_clearing_background_removes_bg_entry() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_background(COSArray.of_cos_floats([0.25]))

    mk.set_background(None)

    assert mk.get_background() is None
    assert mk.get_cos_object().contains_key("BG") is False


def test_wave687_negative_rotation_normalizes_to_canonical_positive_angle() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(-90)

    assert mk.get_normalized_rotation() == 270


def test_wave687_rollover_and_alternate_icon_form_wrappers_use_underlying_streams() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    rollover = COSStream()
    alternate = COSStream()

    mk.set_rollover_icon(PDFormXObject(rollover))
    mk.set_alternate_icon(PDFormXObject(alternate))

    rollover_form = mk.get_rollover_icon_form()
    alternate_form = mk.get_alternate_icon_form()
    assert isinstance(rollover_form, PDFormXObject)
    assert isinstance(alternate_form, PDFormXObject)
    assert rollover_form.get_cos_object() is rollover
    assert alternate_form.get_cos_object() is alternate


def test_wave687_icon_setters_reject_non_stream_values() -> None:
    mk = PDAppearanceCharacteristicsDictionary()

    with pytest.raises(TypeError, match="icon must be"):
        mk.set_alternate_icon(object())
