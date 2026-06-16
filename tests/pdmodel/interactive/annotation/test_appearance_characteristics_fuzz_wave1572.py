"""Fuzz/parity tests for PDAppearanceCharacteristicsDictionary (/MK) and
its /IF PDIconFit sub-dictionary, plus PDAnnotationWidget.get_appearance_
characteristics.

Behavioural parity target: Apache PDFBox 3.0.7
``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary``
(see upstream private ``getColor(COSName)`` arity dispatch and the
caption/rotation getters/setters).

Wave 1572, Agent D.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.color.pd_color import PDColor
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_icon_fit import PDIconFit


def _ac() -> PDAppearanceCharacteristicsDictionary:
    return PDAppearanceCharacteristicsDictionary(COSDictionary())


def _color_array(*vals: float) -> COSArray:
    arr = COSArray()
    for v in vals:
        arr.add(COSFloat(float(v)))
    return arr


# ---------- /R rotation ----------


def test_rotation_default_is_zero():
    assert _ac().get_rotation() == 0


@pytest.mark.parametrize("rot", [0, 90, 180, 270, 360, 450, -90])
def test_rotation_round_trip_preserves_raw_value(rot):
    ac = _ac()
    ac.set_rotation(rot)
    # Upstream getRotation is a plain getInt(R, 0): NO normalization.
    assert ac.get_rotation() == rot


@pytest.mark.parametrize("rot", [45, 1, 91, 200, -45])
def test_rotation_non_multiple_of_90_is_returned_verbatim(rot):
    # Parity: upstream does not validate /R on get; the raw value persists.
    ac = _ac()
    ac.set_rotation(rot)
    assert ac.get_rotation() == rot


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (0, 0),
        (90, 90),
        (180, 180),
        (270, 270),
        (360, 0),
        (450, 90),
        (-90, 270),
        (-360, 0),
        (45, 0),  # non-multiple -> 0
        (1, 0),
        (135, 0),
    ],
)
def test_normalized_rotation(raw, expected):
    ac = _ac()
    ac.set_rotation(raw)
    assert ac.get_normalized_rotation() == expected


# ---------- /BC and /BG colour arity dispatch ----------


@pytest.mark.parametrize(
    ("vals", "cs_instance", "ncomp"),
    [
        ((0.5,), PDDeviceGray.INSTANCE, 1),
        ((0.1, 0.2, 0.3), PDDeviceRGB.INSTANCE, 3),
        ((0.1, 0.2, 0.3, 0.4), PDDeviceCMYK.INSTANCE, 4),
    ],
)
def test_border_colour_arity_dispatch(vals, cs_instance, ncomp):
    ac = _ac()
    ac.get_cos_object().set_item(COSName.get_pdf_name("BC"), _color_array(*vals))
    col = ac.get_border_colour()
    assert col is not None
    assert col.get_color_space() is cs_instance
    assert len(col.get_components()) == ncomp


@pytest.mark.parametrize(
    ("vals", "cs_instance"),
    [
        ((0.5,), PDDeviceGray.INSTANCE),
        ((0.1, 0.2, 0.3), PDDeviceRGB.INSTANCE),
        ((0.1, 0.2, 0.3, 0.4), PDDeviceCMYK.INSTANCE),
    ],
)
def test_background_arity_dispatch(vals, cs_instance):
    ac = _ac()
    ac.get_cos_object().set_item(COSName.get_pdf_name("BG"), _color_array(*vals))
    col = ac.get_background()
    assert col is not None
    assert col.get_color_space() is cs_instance


@pytest.mark.parametrize("vals", [(), (0.1, 0.2), (0.1, 0.2, 0.3, 0.4, 0.5)])
def test_border_colour_non_1_3_4_returns_none(vals):
    # Parity: upstream getColor() returns null for size 0/2/5 (transparent).
    ac = _ac()
    ac.get_cos_object().set_item(COSName.get_pdf_name("BC"), _color_array(*vals))
    assert ac.get_border_colour() is None


def test_empty_border_array_is_transparent_none_but_array_visible():
    # The empty array means "transparent border"; typed getter is None,
    # but the raw escape-hatch still sees the (empty) array.
    ac = _ac()
    ac.get_cos_object().set_item(COSName.get_pdf_name("BC"), COSArray())
    assert ac.get_border_colour() is None
    raw = ac.get_border_colour_array()
    assert raw is not None
    assert raw.size() == 0


def test_missing_colours_return_none():
    ac = _ac()
    assert ac.get_border_colour() is None
    assert ac.get_background() is None
    assert ac.get_border_colour_array() is None
    assert ac.get_background_array() is None


def test_non_array_colour_value_returns_none():
    ac = _ac()
    ac.get_cos_object().set_item(COSName.get_pdf_name("BC"), COSInteger.get(5))
    assert ac.get_border_colour() is None
    assert ac.get_border_colour_array() is None


def test_generic_get_color_matches_dedicated_getters():
    ac = _ac()
    ac.get_cos_object().set_item(
        COSName.get_pdf_name("BC"), _color_array(0.1, 0.2, 0.3)
    )
    via_generic = ac.get_color(COSName.get_pdf_name("BC"))
    via_dedicated = ac.get_border_colour()
    assert via_generic is not None and via_dedicated is not None
    assert via_generic.get_color_space() is via_dedicated.get_color_space()


# ---------- set colour round-trips ----------


@pytest.mark.parametrize(
    ("comps", "cs"),
    [
        ([0.25], PDDeviceGray.INSTANCE),
        ([0.1, 0.5, 0.9], PDDeviceRGB.INSTANCE),
        ([0.1, 0.2, 0.3, 0.4], PDDeviceCMYK.INSTANCE),
    ],
)
def test_set_border_colour_pdcolor_round_trip(comps, cs):
    ac = _ac()
    ac.set_border_colour(PDColor(list(comps), cs))
    out = ac.get_border_colour()
    assert out is not None
    assert out.get_components() == pytest.approx(comps)
    assert out.get_color_space() is cs


def test_set_border_colour_raw_array_round_trip():
    ac = _ac()
    ac.set_border_colour(_color_array(0.2, 0.4, 0.6))
    out = ac.get_border_colour()
    assert out is not None
    assert out.get_color_space() is PDDeviceRGB.INSTANCE


def test_set_border_colour_none_removes_entry():
    ac = _ac()
    ac.set_border_colour(_color_array(0.5))
    assert ac.get_border_colour() is not None
    ac.set_border_colour(None)
    assert ac.get_border_colour() is None
    assert not ac.get_cos_object().contains_key(COSName.get_pdf_name("BC"))


def test_set_background_none_removes_entry():
    ac = _ac()
    ac.set_background(_color_array(0.5, 0.5, 0.5))
    ac.set_background(None)
    assert ac.get_background() is None


def test_set_colour_rejects_bad_type():
    ac = _ac()
    with pytest.raises(TypeError):
        ac.set_border_colour(object())


# ---------- captions /CA /RC /AC ----------


@pytest.mark.parametrize(
    ("getter", "setter"),
    [
        ("get_normal_caption", "set_normal_caption"),
        ("get_rollover_caption", "set_rollover_caption"),
        ("get_alternate_caption", "set_alternate_caption"),
    ],
)
def test_caption_round_trip(getter, setter):
    ac = _ac()
    assert getattr(ac, getter)() is None
    getattr(ac, setter)("OK")
    assert getattr(ac, getter)() == "OK"


def test_captions_are_independent_keys():
    ac = _ac()
    ac.set_normal_caption("N")
    ac.set_rollover_caption("R")
    ac.set_alternate_caption("A")
    assert ac.get_normal_caption() == "N"
    assert ac.get_rollover_caption() == "R"
    assert ac.get_alternate_caption() == "A"


@pytest.mark.parametrize("caption", ["", "Click me", "déjà-vu", "x" * 256])
def test_caption_various_strings(caption):
    ac = _ac()
    ac.set_normal_caption(caption)
    assert ac.get_normal_caption() == caption


def test_caption_stored_as_name_reads_as_none():
    # Parity: upstream getString returns null when /CA is not a COSString
    # (e.g. a malformed PDF storing the caption as a name).
    ac = _ac()
    ac.get_cos_object().set_item(
        COSName.get_pdf_name("CA"), COSName.get_pdf_name("Off")
    )
    assert ac.get_normal_caption() is None


# ---------- /TP text position ----------


def test_text_position_default_zero():
    assert _ac().get_text_position() == 0


@pytest.mark.parametrize(
    "tp",
    [
        PDAppearanceCharacteristicsDictionary.TEXT_POSITION_CAPTION_ONLY,
        PDAppearanceCharacteristicsDictionary.TEXT_POSITION_NO_CAPTION,
        PDAppearanceCharacteristicsDictionary.TEXT_POSITION_CAPTION_BELOW,
        PDAppearanceCharacteristicsDictionary.TEXT_POSITION_CAPTION_ABOVE,
        PDAppearanceCharacteristicsDictionary.TEXT_POSITION_CAPTION_RIGHT,
        PDAppearanceCharacteristicsDictionary.TEXT_POSITION_CAPTION_LEFT,
        PDAppearanceCharacteristicsDictionary.TEXT_POSITION_CAPTION_OVERLAID,
    ],
)
def test_text_position_round_trip(tp):
    ac = _ac()
    ac.set_text_position(tp)
    assert ac.get_text_position() == tp


# ---------- /IF PDIconFit ----------


def test_icon_fit_absent_returns_none():
    assert _ac().get_icon_fit() is None


def test_icon_fit_round_trip_via_pdiconfit():
    ac = _ac()
    fit = PDIconFit()
    fit.set_scale_option(PDIconFit.SCALE_OPTION_NEVER)
    fit.set_scale_type(PDIconFit.SCALE_TYPE_ANAMORPHIC)
    fit.set_fractional_space(0.25, 0.75)
    fit.set_fit_to_bounds(True)
    ac.set_icon_fit(fit)
    out = ac.get_icon_fit()
    assert out is not None
    assert out.get_scale_option() == PDIconFit.SCALE_OPTION_NEVER
    assert out.get_scale_type() == PDIconFit.SCALE_TYPE_ANAMORPHIC
    assert out.get_fractional_space() == pytest.approx((0.25, 0.75))
    assert out.is_fit_to_bounds() is True


def test_icon_fit_set_none_removes():
    ac = _ac()
    ac.set_icon_fit(PDIconFit())
    assert ac.get_icon_fit() is not None
    ac.set_icon_fit(None)
    assert ac.get_icon_fit() is None


def test_icon_fit_defaults_match_pdfbox():
    fit = PDIconFit()
    # Upstream FDFIconFit defaults: SW absent -> "A", S absent -> "P".
    assert fit.get_scale_option() == PDIconFit.SCALE_OPTION_ALWAYS
    assert fit.get_scale_type() == PDIconFit.SCALE_TYPE_PROPORTIONAL
    assert fit.get_fractional_space() == pytest.approx((0.5, 0.5))
    assert fit.is_fit_to_bounds() is False


@pytest.mark.parametrize(
    "opt",
    [
        PDIconFit.SCALE_OPTION_ALWAYS,
        PDIconFit.SCALE_OPTION_ICON_IS_BIGGER,
        PDIconFit.SCALE_OPTION_ICON_IS_SMALLER,
        PDIconFit.SCALE_OPTION_NEVER,
    ],
)
def test_icon_fit_scale_option_round_trip(opt):
    fit = PDIconFit()
    fit.set_scale_option(opt)
    assert fit.get_scale_option() == opt


def test_icon_fit_dont_stretch_is_never_alias():
    fit = PDIconFit()
    assert fit.get_dont_stretch() is False
    fit.set_scale_option(PDIconFit.SCALE_OPTION_NEVER)
    assert fit.get_dont_stretch() is True


def test_icon_fit_has_predicates_distinguish_default_from_explicit():
    fit = PDIconFit()
    assert not fit.has_scale_option()
    assert not fit.has_scale_type()
    assert not fit.has_fractional_space()
    assert not fit.has_fit_to_bounds()
    fit.set_scale_option(PDIconFit.SCALE_OPTION_ALWAYS)
    fit.set_fit_to_bounds(False)
    assert fit.has_scale_option()
    assert fit.has_fit_to_bounds()


def test_icon_fit_fractional_space_short_array_falls_back_to_default():
    d = COSDictionary()
    d.set_item(COSName.get_pdf_name("A"), _color_array(0.3))  # only 1 element
    fit = PDIconFit(d)
    assert fit.get_fractional_space() == pytest.approx((0.5, 0.5))


# ---------- widget /MK integration ----------


def test_widget_missing_mk_returns_none():
    w = PDAnnotationWidget()
    assert w.get_appearance_characteristics() is None
    assert w.has_appearance_characteristics() is False


def test_widget_mk_round_trip():
    w = PDAnnotationWidget()
    ac = _ac()
    ac.set_rotation(90)
    ac.set_normal_caption("Submit")
    w.set_appearance_characteristics(ac)
    assert w.has_appearance_characteristics() is True
    out = w.get_appearance_characteristics()
    assert out is not None
    assert out.get_rotation() == 90
    assert out.get_normal_caption() == "Submit"


def test_widget_mk_shares_backing_dictionary():
    # get_appearance_characteristics wraps the live /MK dict; mutations
    # via the returned object persist on the widget.
    w = PDAnnotationWidget()
    w.set_appearance_characteristics(_ac())
    out = w.get_appearance_characteristics()
    assert out is not None
    out.set_text_position(
        PDAppearanceCharacteristicsDictionary.TEXT_POSITION_CAPTION_BELOW
    )
    again = w.get_appearance_characteristics()
    assert again is not None
    assert again.get_text_position() == 2


def test_widget_set_mk_none_removes():
    w = PDAnnotationWidget()
    w.set_appearance_characteristics(_ac())
    w.set_appearance_characteristics(None)
    assert w.get_appearance_characteristics() is None


def test_widget_non_dict_mk_returns_none():
    w = PDAnnotationWidget()
    w.get_cos_object().set_item(COSName.get_pdf_name("MK"), COSInteger.get(1))
    assert w.get_appearance_characteristics() is None
    assert w.has_appearance_characteristics() is False
