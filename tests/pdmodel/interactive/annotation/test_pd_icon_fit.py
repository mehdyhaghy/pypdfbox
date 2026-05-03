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


# ---------- value-tuple class constants ----------


def test_scale_option_values_tuple_in_declaration_order() -> None:
    assert PDIconFit.SCALE_OPTION_VALUES == ("A", "B", "S", "N")
    # Tuple is hashable + iterable for validation use-cases.
    assert isinstance(PDIconFit.SCALE_OPTION_VALUES, tuple)
    assert PDIconFit.SCALE_OPTION_ALWAYS in PDIconFit.SCALE_OPTION_VALUES
    assert PDIconFit.SCALE_OPTION_NEVER in PDIconFit.SCALE_OPTION_VALUES


def test_scale_type_values_tuple_in_declaration_order() -> None:
    assert PDIconFit.SCALE_TYPE_VALUES == ("A", "P")
    assert isinstance(PDIconFit.SCALE_TYPE_VALUES, tuple)


# ---------- has_* predicates ----------


def test_has_scale_option_distinguishes_default_from_missing() -> None:
    icon_fit = PDIconFit()
    assert icon_fit.has_scale_option() is False
    # Default getter still returns Always.
    assert icon_fit.get_scale_option() == "A"
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_ALWAYS)
    assert icon_fit.has_scale_option() is True
    assert icon_fit.get_scale_option() == "A"


def test_has_scale_type_distinguishes_default_from_missing() -> None:
    icon_fit = PDIconFit()
    assert icon_fit.has_scale_type() is False
    icon_fit.set_scale_type(PDIconFit.SCALE_TYPE_PROPORTIONAL)
    assert icon_fit.has_scale_type() is True


def test_has_fractional_space_distinguishes_default_from_missing() -> None:
    icon_fit = PDIconFit()
    assert icon_fit.has_fractional_space() is False
    icon_fit.set_fractional_space(0.5, 0.5)
    assert icon_fit.has_fractional_space() is True


def test_has_fit_to_bounds_distinguishes_default_from_missing() -> None:
    icon_fit = PDIconFit()
    assert icon_fit.has_fit_to_bounds() is False
    icon_fit.set_fit_to_bounds(False)
    assert icon_fit.has_fit_to_bounds() is True


# ---------- None-removal semantics ----------


def test_set_scale_option_none_removes_entry() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_NEVER)
    assert icon_fit.has_scale_option() is True
    icon_fit.set_scale_option(None)
    assert icon_fit.has_scale_option() is False
    # Default reasserts.
    assert icon_fit.get_scale_option() == "A"


def test_set_scale_type_none_removes_entry() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_scale_type(PDIconFit.SCALE_TYPE_ANAMORPHIC)
    assert icon_fit.has_scale_type() is True
    icon_fit.set_scale_type(None)
    assert icon_fit.has_scale_type() is False
    assert icon_fit.get_scale_type() == "P"


# ---------- /SW predicate helpers ----------


def test_is_scale_predicates_track_default() -> None:
    icon_fit = PDIconFit()
    # Default is Always.
    assert icon_fit.is_scale_always() is True
    assert icon_fit.is_scale_when_bigger() is False
    assert icon_fit.is_scale_when_smaller() is False
    assert icon_fit.is_scale_never() is False


def test_is_scale_predicates_round_trip_each_value() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_ICON_IS_BIGGER)
    assert icon_fit.is_scale_when_bigger() is True
    assert icon_fit.is_scale_always() is False

    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_ICON_IS_SMALLER)
    assert icon_fit.is_scale_when_smaller() is True
    assert icon_fit.is_scale_when_bigger() is False

    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_NEVER)
    assert icon_fit.is_scale_never() is True
    # get_dont_stretch still tracks /SW == N.
    assert icon_fit.get_dont_stretch() is True


# ---------- /S predicate helpers ----------


def test_is_proportional_default_true_anamorphic_round_trips() -> None:
    icon_fit = PDIconFit()
    assert icon_fit.is_proportional() is True
    assert icon_fit.is_anamorphic() is False

    icon_fit.set_scale_type(PDIconFit.SCALE_TYPE_ANAMORPHIC)
    assert icon_fit.is_anamorphic() is True
    assert icon_fit.is_proportional() is False


# ---------- get_fractional_space convenience ----------


def test_get_fractional_space_default_centered_tuple() -> None:
    icon_fit = PDIconFit()
    assert icon_fit.get_fractional_space() == (0.5, 0.5)


def test_get_fractional_space_returns_set_value_as_tuple() -> None:
    import pytest

    icon_fit = PDIconFit()
    icon_fit.set_fractional_space(0.1, 0.9)
    pos = icon_fit.get_fractional_space()
    assert isinstance(pos, tuple)
    # COSFloat round-trips through 32-bit floats.
    assert pos[0] == pytest.approx(0.1, rel=1e-6)
    assert pos[1] == pytest.approx(0.9, rel=1e-6)


def test_fractional_space_short_array_falls_back_to_default() -> None:
    # If /A is malformed (single element), accessors must not raise.
    icon_fit = PDIconFit()
    short = COSArray([COSFloat(0.7)])
    icon_fit.get_cos_object().set_item(COSName.get_pdf_name("A"), short)
    assert icon_fit.get_fractional_space() == (0.5, 0.5)
    assert icon_fit.get_fractional_space_x() == 0.5
    assert icon_fit.get_fractional_space_y() == 0.5
    # The entry exists even though it's malformed.
    assert icon_fit.has_fractional_space() is True


# ---------- repr ----------


def test_repr_includes_all_field_summaries() -> None:
    icon_fit = PDIconFit()
    icon_fit.set_scale_option(PDIconFit.SCALE_OPTION_NEVER)
    icon_fit.set_scale_type(PDIconFit.SCALE_TYPE_ANAMORPHIC)
    # 0.25 and 0.75 are exactly representable in IEEE 754 single precision
    # so the COSFloat round-trip is lossless.
    icon_fit.set_fractional_space(0.25, 0.75)
    icon_fit.set_fit_to_bounds(True)
    text = repr(icon_fit)
    assert "PDIconFit" in text
    assert "'N'" in text
    assert "'A'" in text
    assert "0.25" in text
    assert "0.75" in text
    assert "True" in text
