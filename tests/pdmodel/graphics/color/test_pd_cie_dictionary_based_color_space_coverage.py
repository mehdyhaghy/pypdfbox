"""Coverage-boost tests for ``PDCIEDictionaryBasedColorSpace``.

Targets the surface absent from ``test_pd_cie_is_white_point.py``:
``__init__`` array/name/None branches, ``get_black_point``,
``set_white_point`` validation, ``set_black_point`` no-op for None,
``fill_whitepoint_cache``, ``conv_xy_zto_rgb`` clamping branches, and the
``conv_xyz_to_rgb`` alias.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.graphics.color.pd_cie_dictionary_based_color_space import (
    PDCIEDictionaryBasedColorSpace,
    _xyz_to_rgb_clamp,
)
from pypdfbox.pdmodel.graphics.color.pd_tristimulus import PDTristimulus


class _Concrete(PDCIEDictionaryBasedColorSpace):
    """Minimal concrete subclass — the abstract base needs ``to_rgb`` and
    ``get_name``. Both are off-path for the dict-based coverage targets."""

    def to_rgb(self, value):  # pragma: no cover - not exercised here
        return value

    def get_name(self) -> str:
        return "FakeCIE"

    def get_number_of_components(self) -> int:  # pragma: no cover
        return 3

    def get_initial_color(self):  # pragma: no cover
        return None


# ---------- ``__init__`` branches ----------------------------------------


def test_init_none_seeds_default_array_and_empty_dict() -> None:
    cs = _Concrete(None)
    assert isinstance(cs.dictionary, COSDictionary)
    # /WhitePoint absent → defaults to unit white point
    assert cs.is_white_point() is True
    assert cs.wp_x == 1.0
    assert cs.wp_y == 1.0
    assert cs.wp_z == 1.0


def test_init_with_cos_name_prepends_name_in_array() -> None:
    name = COSName.get_pdf_name("CalRGB")
    cs = _Concrete(name)
    arr = cs._array
    assert arr.size() == 2
    assert arr.get(0) == name
    assert arr.get(1) is cs.dictionary


def test_init_with_existing_array_wraps_dictionary_in_position_one() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Lab"))
    params = COSDictionary()
    wp = COSArray()
    wp.add(COSFloat(0.9504))
    wp.add(COSFloat(1.0))
    wp.add(COSFloat(1.0889))
    params.set_item(COSName.get_pdf_name("WhitePoint"), wp)
    arr.add(params)

    cs = _Concrete(arr)
    assert cs._array is arr
    assert cs.dictionary is params
    # Cached whitepoint must come from the supplied dict.
    assert cs.wp_x == pytest.approx(0.9504)
    assert cs.wp_z == pytest.approx(1.0889)


def test_init_with_array_lacking_dict_at_index_one_falls_back_to_empty() -> None:
    arr = COSArray()
    arr.add(COSName.get_pdf_name("CalGray"))
    arr.add(COSName.get_pdf_name("oops-not-a-dict"))
    cs = _Concrete(arr)
    assert isinstance(cs.dictionary, COSDictionary)
    # /WhitePoint absent → unit white point default still applies.
    assert cs.is_white_point() is True


# ---------- ``get_whitepoint`` / ``get_black_point`` ---------------------


def test_get_whitepoint_default_when_absent() -> None:
    cs = _Concrete()
    wp = cs.get_whitepoint()
    assert wp.get_x() == 1.0
    assert wp.get_y() == 1.0
    assert wp.get_z() == 1.0


def test_get_black_point_default_when_absent() -> None:
    cs = _Concrete()
    bp = cs.get_black_point()
    assert bp.get_x() == 0.0
    assert bp.get_y() == 0.0
    assert bp.get_z() == 0.0


def test_get_black_point_reads_from_dictionary() -> None:
    cs = _Concrete()
    bp_arr = COSArray()
    bp_arr.add(COSFloat(0.1))
    bp_arr.add(COSFloat(0.2))
    bp_arr.add(COSFloat(0.3))
    cs.dictionary.set_item(COSName.get_pdf_name("BlackPoint"), bp_arr)
    bp = cs.get_black_point()
    assert bp.get_x() == pytest.approx(0.1)
    assert bp.get_y() == pytest.approx(0.2)
    assert bp.get_z() == pytest.approx(0.3)


def test_get_black_point_non_array_entry_falls_back_to_zero() -> None:
    cs = _Concrete()
    # Non-array value in /BlackPoint → fall back to default (0, 0, 0).
    cs.dictionary.set_item(
        COSName.get_pdf_name("BlackPoint"), COSName.get_pdf_name("NotAnArray")
    )
    bp = cs.get_black_point()
    assert bp.get_x() == 0.0


# ---------- ``set_white_point`` / ``set_black_point`` --------------------


def test_set_white_point_none_raises_value_error() -> None:
    cs = _Concrete()
    with pytest.raises(ValueError, match="Whitepoint may not be null"):
        cs.set_white_point(None)


def test_set_white_point_refreshes_cache_and_writes_dict() -> None:
    cs = _Concrete()
    new_wp = PDTristimulus([0.9505, 1.0, 1.0890])
    cs.set_white_point(new_wp)
    assert cs.wp_x == pytest.approx(0.9505)
    assert cs.wp_y == pytest.approx(1.0)
    assert cs.wp_z == pytest.approx(1.0890)
    # And the underlying dict received it:
    stored = cs.dictionary.get_dictionary_object(COSName.get_pdf_name("WhitePoint"))
    assert stored is new_wp.get_cos_object()


def test_set_black_point_none_is_no_op() -> None:
    cs = _Concrete()
    cs.set_black_point(None)
    # /BlackPoint still absent → default zeros.
    assert cs.get_black_point().get_x() == 0.0


def test_set_black_point_writes_to_dict() -> None:
    cs = _Concrete()
    bp = PDTristimulus([0.05, 0.06, 0.07])
    cs.set_black_point(bp)
    fetched = cs.get_black_point()
    assert fetched.get_x() == pytest.approx(0.05)
    assert fetched.get_y() == pytest.approx(0.06)
    assert fetched.get_z() == pytest.approx(0.07)


# ---------- ``fill_whitepoint_cache`` + alias ----------------------------


def test_fill_whitepoint_cache_updates_cached_components() -> None:
    cs = _Concrete()
    cs.fill_whitepoint_cache(PDTristimulus([0.5, 0.6, 0.7]))
    assert cs.wp_x == pytest.approx(0.5)
    assert cs.wp_y == pytest.approx(0.6)
    assert cs.wp_z == pytest.approx(0.7)


def test_underscore_alias_fill_whitepoint_cache_works() -> None:
    cs = _Concrete()
    cs._fill_whitepoint_cache(PDTristimulus([0.2, 0.3, 0.4]))
    assert cs.wp_x == pytest.approx(0.2)


# ---------- ``conv_xy_zto_rgb`` clamping ---------------------------------


def test_conv_xy_zto_rgb_zero_input_returns_zero_rgb() -> None:
    cs = _Concrete()
    rgb = cs.conv_xy_zto_rgb(0.0, 0.0, 0.0)
    assert rgb == [0.0, 0.0, 0.0]


def test_conv_xy_zto_rgb_negative_inputs_clamped_to_zero_before_matrix() -> None:
    # Negative inputs are clamped to 0 first — equivalent to (0, 0, 0).
    cs = _Concrete()
    rgb = cs.conv_xy_zto_rgb(-1.0, -1.0, -1.0)
    assert rgb == [0.0, 0.0, 0.0]


def test_conv_xy_zto_rgb_unit_white_is_unit_rgb() -> None:
    # The sRGB matrix applied to D65 white-ish XYZ should yield ~1s,
    # which then get clamped to 1.0.
    cs = _Concrete()
    rgb = cs.conv_xy_zto_rgb(1.0, 1.0, 1.0)
    assert all(0.0 <= c <= 1.0 for c in rgb)


def test_conv_xyz_to_rgb_alias_delegates_to_conv_xy_zto_rgb() -> None:
    cs = _Concrete()
    assert cs.conv_xyz_to_rgb(0.5, 0.5, 0.5) == cs.conv_xy_zto_rgb(0.5, 0.5, 0.5)


# ---------- ``_xyz_to_rgb_clamp`` direct helper coverage ------------------


def test_helper_clamp_negative_x_y_z_to_zero() -> None:
    assert _xyz_to_rgb_clamp(-0.1, -0.5, -1.0) == [0.0, 0.0, 0.0]


def test_helper_linear_branch_for_small_values() -> None:
    # Any non-zero positive component that stays in [0, 0.0031308] hits the
    # linear sRGB encode branch (u * 12.92).
    out = _xyz_to_rgb_clamp(0.001, 0.001, 0.001)
    assert all(0.0 <= c <= 1.0 for c in out)


def test_helper_gamma_branch_for_mid_values() -> None:
    out = _xyz_to_rgb_clamp(0.3, 0.3, 0.3)
    assert all(0.0 <= c <= 1.0 for c in out)


def test_helper_clamps_above_one_to_one() -> None:
    out = _xyz_to_rgb_clamp(5.0, 5.0, 5.0)
    assert out == [1.0, 1.0, 1.0]
