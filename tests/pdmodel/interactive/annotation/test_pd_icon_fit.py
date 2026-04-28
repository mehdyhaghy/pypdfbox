from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_icon_fit import PDIconFit


def test_default_constructor_creates_empty_dict() -> None:
    icon_fit = PDIconFit()
    assert isinstance(icon_fit.get_cos_object(), COSDictionary)
    assert len(icon_fit.get_cos_object()) == 0


def test_constructor_with_dict_preserves_identity() -> None:
    d = COSDictionary()
    icon_fit = PDIconFit(d)
    assert icon_fit.get_cos_object() is d


def test_scale_option_default_is_always() -> None:
    assert PDIconFit().get_scale_option() == "A"
    assert PDIconFit().get_scale_option() == PDIconFit.SCALE_OPTION_ALWAYS


def test_scale_option_round_trip() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_ICON_IS_BIGGER)
    assert icon_fit.get_scale_option() == "B"
    sw = icon_fit.get_cos_object().get_dictionary_object(COSName.get_pdf_name("SW"))
    assert isinstance(sw, COSName)
    assert sw.get_name() == "B"


def test_scale_option_never_and_smaller() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_scale_option("N")
    assert icon_fit.get_scale_option() == "N"
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_ICON_IS_SMALLER)
    assert icon_fit.get_scale_option() == "S"


def test_scale_type_default_is_proportional() -> None:
    assert PDIconFit().get_scale_type() == "P"
    assert PDIconFit().get_scale_type() == PDIconFit.SCALE_TYPE_PROPORTIONAL


def test_scale_type_round_trip() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_scale_type(PDIconFit.SCALE_TYPE_ANAMORPHIC)
    assert icon_fit.get_scale_type() == "A"
    s = icon_fit.get_cos_object().get_dictionary_object(COSName.get_pdf_name("S"))
    assert isinstance(s, COSName)
    assert s.get_name() == "A"


def test_fractional_space_defaults_to_centre() -> None:
    icon_fit = PDIconFit()
    assert icon_fit.get_fractional_space_x() == 0.5
    assert icon_fit.get_fractional_space_y() == 0.5


def test_fractional_space_round_trip() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_fractional_space(0.25, 0.75)
    assert icon_fit.get_fractional_space_x() == 0.25
    assert icon_fit.get_fractional_space_y() == 0.75
    arr = icon_fit.get_cos_object().get_dictionary_object(COSName.get_pdf_name("A"))
    assert isinstance(arr, COSArray)
    assert arr.size() == 2
    assert isinstance(arr.get(0), COSFloat)
    assert isinstance(arr.get(1), COSFloat)


def test_fit_to_bounds_default_false() -> None:
    assert PDIconFit().is_fit_to_bounds() is False


def test_fit_to_bounds_round_trip() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_fit_to_bounds(True)
    assert icon_fit.is_fit_to_bounds() is True
    fb = icon_fit.get_cos_object().get_dictionary_object(COSName.get_pdf_name("FB"))
    assert isinstance(fb, COSBoolean)
    assert fb.value is True
    icon_fit.set_fit_to_bounds(False)
    assert icon_fit.is_fit_to_bounds() is False


def test_dont_stretch_alias_tracks_scale_option_never() -> None:
    icon_fit = PDIconFit()
    assert icon_fit.get_dont_stretch() is False
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_NEVER)
    assert icon_fit.get_dont_stretch() is True
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_ALWAYS)
    assert icon_fit.get_dont_stretch() is False


def test_constants_match_pdf_spec_letters() -> None:
    assert PDIconFit.SCALE_OPTION_ALWAYS == "A"
    assert PDIconFit.SCALE_OPTION_ICON_IS_BIGGER == "B"
    assert PDIconFit.SCALE_OPTION_ICON_IS_SMALLER == "S"
    assert PDIconFit.SCALE_OPTION_NEVER == "N"
    assert PDIconFit.SCALE_TYPE_ANAMORPHIC == "A"
    assert PDIconFit.SCALE_TYPE_PROPORTIONAL == "P"
