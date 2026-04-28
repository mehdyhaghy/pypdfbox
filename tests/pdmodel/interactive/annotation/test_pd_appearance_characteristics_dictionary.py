from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
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


# ---------- /BC border colour ----------


def test_border_colour_default_none() -> None:
    assert PDAppearanceCharacteristicsDictionary().get_border_colour() is None


def test_border_colour_round_trip_grey() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    bc = COSArray.of_cos_floats([0.5])
    mk.set_border_colour(bc)
    assert mk.get_border_colour() is bc


def test_border_colour_round_trip_cmyk() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    bc = COSArray.of_cos_floats([0.0, 0.5, 1.0, 0.25])
    mk.set_border_colour(bc)
    assert mk.get_border_colour() is bc
    assert len(mk.get_border_colour()) == 4


def test_border_colour_clear_via_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(COSArray.of_cos_floats([1.0, 0.0, 0.0]))
    mk.set_border_colour(None)
    assert mk.get_border_colour() is None
    assert not mk.get_cos_object().contains_key(COSName.get_pdf_name("BC"))


def test_border_colour_empty_array_signifies_no_colour() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_border_colour(COSArray())
    rt = mk.get_border_colour()
    assert isinstance(rt, COSArray)
    assert len(rt) == 0


# ---------- /BG background colour ----------


def test_background_default_none() -> None:
    assert PDAppearanceCharacteristicsDictionary().get_background() is None


def test_background_round_trip_rgb() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    bg = COSArray.of_cos_floats([0.1, 0.2, 0.3])
    mk.set_background(bg)
    assert mk.get_background() is bg


def test_background_clear_via_none() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_background(COSArray.of_cos_floats([0.5]))
    mk.set_background(None)
    assert mk.get_background() is None


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
