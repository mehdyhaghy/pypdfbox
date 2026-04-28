"""Approximate upstream parity tests for
``org.apache.pdfbox.pdmodel.interactive.annotation.PDAppearanceCharacteristicsDictionary``
(PDFBox 3.0.x).

Upstream PDFBox 3.0.x has no dedicated
``PDAppearanceCharacteristicsDictionaryTest.java``; the dictionary is
exercised implicitly by ``PDPushButtonTest`` and ``PDAcroFormTest``.
The cases below cover the upstream-documented defaults and the
single-source round-trips visible in those upstream tests.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_icon_fit import PDIconFit


def test_default_rotation_is_zero() -> None:
    # PDFBox: getRotation() returns 0 when /R is absent.
    assert PDAppearanceCharacteristicsDictionary().get_rotation() == 0


def test_set_rotation_writes_r_entry() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_rotation(90)
    assert mk.get_cos_object().get_int(COSName.get_pdf_name("R")) == 90


def test_default_text_position_is_zero() -> None:
    # PDFBox: getCaptionPosition() returns 0 ("caption only") when /TP absent.
    assert PDAppearanceCharacteristicsDictionary().get_text_position() == 0


def test_default_normal_caption_is_null() -> None:
    # assertNull(mk.getNormalCaption()) — upstream default.
    assert PDAppearanceCharacteristicsDictionary().get_normal_caption() is None


def test_default_border_colour_is_null() -> None:
    # assertNull(mk.getBorderColour()) when /BC absent.
    assert PDAppearanceCharacteristicsDictionary().get_border_colour() is None


def test_default_background_is_null() -> None:
    # assertNull(mk.getBackground()) when /BG absent.
    assert PDAppearanceCharacteristicsDictionary().get_background() is None


def test_default_normal_icon_is_null() -> None:
    assert PDAppearanceCharacteristicsDictionary().get_normal_icon() is None


def test_set_normal_caption_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    mk.set_normal_caption("Submit")
    assert mk.get_normal_caption() == "Submit"


def test_construct_with_provided_dictionary_preserves_identity() -> None:
    # PDFBox constructor sets the underlying dictionary reference unchanged.
    d = COSDictionary()
    mk = PDAppearanceCharacteristicsDictionary(d)
    assert mk.get_cos_object() is d


def test_set_border_colour_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    bc = COSArray.of_cos_floats([0.0, 0.0, 0.0])
    mk.set_border_colour(bc)
    assert mk.get_border_colour() is bc


def test_default_icon_fit_is_null() -> None:
    # assertNull(mk.getIconFit()) when /IF absent.
    assert PDAppearanceCharacteristicsDictionary().get_icon_fit() is None


def test_set_icon_fit_round_trip() -> None:
    mk = PDAppearanceCharacteristicsDictionary()
    icon_fit = PDIconFit()
    icon_fit.set_scale_type(PDIconFit.SCALE_TYPE_PROPORTIONAL)
    mk.set_icon_fit(icon_fit)
    rt = mk.get_icon_fit()
    assert rt is not None
    assert rt.get_scale_type() == "P"


def test_pd_icon_fit_default_scale_option_is_always() -> None:
    # PDIconFit upstream default: getScaleOption() == "A".
    assert PDIconFit().get_scale_option() == "A"


def test_pd_icon_fit_default_scale_type_is_proportional() -> None:
    # PDIconFit upstream default: getScale() == "P".
    assert PDIconFit().get_scale_type() == "P"


def test_pd_icon_fit_default_fit_to_bounds_is_false() -> None:
    assert PDIconFit().is_fit_to_bounds() is False
