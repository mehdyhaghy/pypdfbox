from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.interactive.annotation import PDIconFit
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)


# ---------- /R rotation ----------


def test_rotation_default_zero() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_rotation() == 0


def test_rotation_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(180)
    assert mk.get_rotation() == 180
    assert mk.get_cos_object().get_int(COSName.get_pdf_name("R")) == 180


def test_rotation_negative_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(-90)
    assert mk.get_rotation() == -90


def test_rotation_constants_match_spec() -> None:
    """``/R`` constants line up with PDF 32000-1 §12.5.6.19 Table 189
    counter-clockwise multiples of 90."""
    assert PDAppearanceCharacteristicsDictionary.ROTATION_NONE == 0
    assert PDAppearanceCharacteristicsDictionary.ROTATION_LEFT == 90
    assert PDAppearanceCharacteristicsDictionary.ROTATION_UPSIDE_DOWN == 180
    assert PDAppearanceCharacteristicsDictionary.ROTATION_RIGHT == 270


def test_rotation_constants_round_trip_via_setter() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    for c in (
        PDAppearanceCharacteristicsDictionary.ROTATION_NONE,
        PDAppearanceCharacteristicsDictionary.ROTATION_LEFT,
        PDAppearanceCharacteristicsDictionary.ROTATION_UPSIDE_DOWN,
        PDAppearanceCharacteristicsDictionary.ROTATION_RIGHT,
    ):
        mk.set_rotation(c)
        assert mk.get_rotation() == c
        assert mk.get_normalized_rotation() == c


def test_normalized_rotation_default_zero() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_normalized_rotation() == 0


def test_normalized_rotation_reduces_modulo_360() -> None:
    """Values >= 360 collapse to their canonical equivalent."""
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(450)  # 450 % 360 == 90
    assert mk.get_normalized_rotation() == 90
    mk.set_rotation(720)  # full revolution(s) → 0
    assert mk.get_normalized_rotation() == 0
    mk.set_rotation(900)  # 900 % 360 == 180
    assert mk.get_normalized_rotation() == 180


def test_normalized_rotation_handles_negative() -> None:
    """Counter-clockwise convention: -90 is equivalent to 270."""
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(-90)
    assert mk.get_normalized_rotation() == 270
    mk.set_rotation(-180)
    assert mk.get_normalized_rotation() == 180
    mk.set_rotation(-450)  # -450 mod 360 == 270
    assert mk.get_normalized_rotation() == 270


def test_normalized_rotation_non_multiple_of_90_returns_zero() -> None:
    """Spec mandates ``/R`` be a multiple of 90; non-canonical values are
    treated as 0 by appearance generators."""
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(45)
    assert mk.get_normalized_rotation() == 0
    mk.set_rotation(123)
    assert mk.get_normalized_rotation() == 0


# ---------- /BC border colour ----------


def test_border_colour_default_none() -> None:
    assert PDAppearanceCharacteristicsDictionary().get_border_colour() is None


def test_border_colour_round_trip_grey() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    color = PDColor([0.5], PDDeviceGray.INSTANCE)
    mk.set_border_colour(color)
    rt = mk.get_border_colour()
    assert isinstance(rt, PDColor)
    assert rt.get_color_space() is PDDeviceGray.INSTANCE
    assert rt.get_components() == [0.5]


def test_border_colour_round_trip_rgb() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    color = PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    mk.set_border_colour(color)
    rt = mk.get_border_colour()
    assert isinstance(rt, PDColor)
    assert rt.get_color_space() is PDDeviceRGB.INSTANCE
    assert rt.get_components() == pytest.approx([0.1, 0.2, 0.3])


def test_border_colour_round_trip_cmyk() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    color = PDColor([0.0, 0.5, 1.0, 0.25], PDDeviceCMYK.INSTANCE)
    mk.set_border_colour(color)
    rt = mk.get_border_colour()
    assert isinstance(rt, PDColor)
    assert rt.get_color_space() is PDDeviceCMYK.INSTANCE
    assert rt.get_components() == [0.0, 0.5, 1.0, 0.25]


def test_border_colour_clear_via_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(PDColor([1.0, 0.0, 0.0], PDDeviceRGB.INSTANCE))
    mk.set_border_colour(None)
    assert mk.get_border_colour() is None
    assert not mk.get_cos_object().contains_key(COSName.get_pdf_name("BC"))


def test_border_colour_zero_or_two_components_is_none() -> None:
    """Per upstream's ``getColor()`` switch: only 1, 3, 4 components map
    to a typed ``PDColor``; other arities yield ``None``."""
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(COSArray())
    assert mk.get_border_colour() is None
    mk.set_border_colour(COSArray.of_cos_floats([0.5, 0.5]))
    assert mk.get_border_colour() is None


def test_border_colour_array_returns_raw_cos_array() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    raw = COSArray.of_cos_floats([0.5, 0.5, 0.5])
    mk.set_border_colour(raw)
    assert mk.get_border_colour_array() is raw


# ---------- /BG background colour ----------


def test_background_default_none() -> None:
    assert PDAppearanceCharacteristicsDictionary().get_background() is None


def test_background_round_trip_rgb() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    color = PDColor([0.1, 0.2, 0.3], PDDeviceRGB.INSTANCE)
    mk.set_background(color)
    rt = mk.get_background()
    assert isinstance(rt, PDColor)
    assert rt.get_components() == pytest.approx([0.1, 0.2, 0.3])


def test_background_clear_via_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_background(PDColor([0.5], PDDeviceGray.INSTANCE))
    mk.set_background(None)
    assert mk.get_background() is None


def test_background_array_returns_raw_cos_array() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    raw = COSArray.of_cos_floats([0.0, 0.5, 1.0, 0.0])
    mk.set_background(raw)
    assert mk.get_background_array() is raw
    typed = mk.get_background()
    assert isinstance(typed, PDColor)
    assert typed.get_color_space() is PDDeviceCMYK.INSTANCE


# ---------- /CA /RC /AC captions ----------


def test_captions_default_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_normal_caption() is None
    assert mk.get_rollover_caption() is None
    assert mk.get_alternate_caption() is None


def test_captions_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_normal_caption("OK")
    mk.set_rollover_caption("Hover")
    mk.set_alternate_caption("Down")
    assert mk.get_normal_caption() == "OK"
    assert mk.get_rollover_caption() == "Hover"
    assert mk.get_alternate_caption() == "Down"


def test_captions_clear_via_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_normal_caption("OK")
    mk.set_normal_caption(None)
    assert mk.get_normal_caption() is None


# ---------- /I /RI /IX icons ----------


def test_icons_default_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert mk.get_normal_icon() is None
    assert mk.get_rollover_icon() is None
    assert mk.get_alternate_icon() is None
    assert mk.get_normal_icon_form() is None


def test_normal_icon_accepts_raw_cos_stream() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    stream = COSStream()
    mk.set_normal_icon(stream)
    assert mk.get_normal_icon() is stream


def test_normal_icon_accepts_form_xobject() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    form = PDFormXObject(COSStream())
    mk.set_normal_icon(form)
    # The underlying stream is the form's COSStream.
    assert mk.get_normal_icon() is form.get_cos_object()


def test_normal_icon_form_wrapper() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    stream = COSStream()
    mk.set_normal_icon(stream)
    wrapped = mk.get_normal_icon_form()
    assert isinstance(wrapped, PDFormXObject)
    assert wrapped.get_cos_object() is stream


def test_rollover_and_alternate_icon_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    ri = COSStream()
    ix = COSStream()
    mk.set_rollover_icon(ri)
    mk.set_alternate_icon(ix)
    assert mk.get_rollover_icon() is ri
    assert mk.get_alternate_icon() is ix


def test_icons_clear_via_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_normal_icon(COSStream())
    mk.set_rollover_icon(COSStream())
    mk.set_alternate_icon(COSStream())
    mk.set_normal_icon(None)
    mk.set_rollover_icon(None)
    mk.set_alternate_icon(None)
    assert mk.get_normal_icon() is None
    assert mk.get_rollover_icon() is None
    assert mk.get_alternate_icon() is None


def test_set_icon_rejects_invalid_type() -> None:
    import pytest

    mk = PDAppearanceCharacteristicsDictionary()
    with pytest.raises(TypeError):
        mk.set_normal_icon(42)  # type: ignore[arg-type]


# ---------- /IF icon fit ----------


def test_icon_fit_default_none() -> None:
    assert PDAppearanceCharacteristicsDictionary().get_icon_fit() is None


def test_icon_fit_round_trip_via_pd_icon_fit() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    icon_fit = PDIconFit()
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_ICON_IS_BIGGER)
    mk.set_icon_fit(icon_fit)
    rt = mk.get_icon_fit()
    assert isinstance(rt, PDIconFit)
    assert rt.get_cos_object() is icon_fit.get_cos_object()
    assert rt.get_scale_option() == "B"


def test_icon_fit_round_trip_via_cos_dictionary() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    raw = COSDictionary()
    mk.set_icon_fit(raw)
    rt = mk.get_icon_fit()
    assert isinstance(rt, PDIconFit)
    assert rt.get_cos_object() is raw


def test_icon_fit_clear_via_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_icon_fit(PDIconFit())
    mk.set_icon_fit(None)
    assert mk.get_icon_fit() is None


# ---------- /TP text position ----------


def test_text_position_default_zero() -> None:
    assert PDAppearanceCharacteristicsDictionary().get_text_position() == 0


def test_text_position_all_seven_codes_round_trip() -> None:
    for tp in range(0, 7):
        mk = PDAppearanceCharacteristicsDictionary()
        mk.set_text_position(tp)
        assert mk.get_text_position() == tp


def test_text_position_constants_match_spec() -> None:
    cls = PDAppearanceCharacteristicsDictionary
    assert cls.TEXT_POSITION_CAPTION_ONLY == 0
    assert cls.TEXT_POSITION_NO_CAPTION == 1
    assert cls.TEXT_POSITION_CAPTION_BELOW == 2
    assert cls.TEXT_POSITION_CAPTION_ABOVE == 3
    assert cls.TEXT_POSITION_CAPTION_RIGHT == 4
    assert cls.TEXT_POSITION_CAPTION_LEFT == 5
    assert cls.TEXT_POSITION_CAPTION_OVERLAID == 6


def test_text_position_constants_round_trip_via_setter() -> None:
    cls = PDAppearanceCharacteristicsDictionary
    mk = cls()
    mk.set_text_position(cls.TEXT_POSITION_CAPTION_OVERLAID)
    assert mk.get_text_position() == 6


# ---------- constructor / cos object ----------


def test_default_constructor_creates_empty_dict() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    assert isinstance(mk.get_cos_object(), COSDictionary)
    assert len(mk.get_cos_object()) == 0


def test_constructor_with_dict_preserves_identity() -> None:
    d = COSDictionary()
    mk = PDAppearanceCharacteristicsDictionary(d)
    assert mk.get_cos_object() is d


# ---------- export from package ----------


def test_re_exported_from_package() -> None:
    from pypdfbox.pdmodel.interactive import annotation

    assert annotation.PDAppearanceCharacteristicsDictionary is (
        PDAppearanceCharacteristicsDictionary
    )
    assert annotation.PDIconFit is PDIconFit
