"""Accessor tests for ``Type1Font`` Private-dict + top-level ID surface
covered in Wave 193: ``get_unique_id``, ``get_stroke_width``,
``get_font_id``, and the Private-dict cluster (``get_blue_values``,
``get_other_blues``, ``get_family_blues``, ``get_family_other_blues``,
``get_blue_scale``, ``get_blue_shift``, ``get_blue_fuzz``,
``get_std_hw``, ``get_std_vw``, ``get_stem_snap_h``, ``get_stem_snap_v``,
``is_force_bold``, ``get_language_group``, ``get_len_iv``).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font


class _FakeT1:
    def __init__(self, font: dict[str, Any]) -> None:
        self.font = font

    def __getitem__(self, key: str) -> Any:
        return self.font[key]


def _font_with(
    top: dict[str, Any] | None = None,
    private: dict[str, Any] | None = None,
) -> Type1Font:
    fd: dict[str, Any] = {"FontName": "TestPS"}
    if top:
        fd.update(top)
    if private is not None:
        fd["Private"] = private
    f = Type1Font()
    f._t1 = _FakeT1(fd)
    return f


# ---------- get_unique_id ----------


def test_get_unique_id_returns_int() -> None:
    f = _font_with(top={"UniqueID": 12345})
    assert f.get_unique_id() == 12345


def test_get_unique_id_default_zero_when_missing() -> None:
    f = _font_with()
    assert f.get_unique_id() == 0


def test_get_unique_id_zero_for_empty_program() -> None:
    assert Type1Font().get_unique_id() == 0


def test_get_unique_id_coerces_numeric_strings() -> None:
    f = _font_with(top={"UniqueID": "42"})
    assert f.get_unique_id() == 42


def test_get_unique_id_default_when_garbage() -> None:
    f = _font_with(top={"UniqueID": "not-an-int"})
    assert f.get_unique_id() == 0


# ---------- get_stroke_width ----------


def test_get_stroke_width_returns_float() -> None:
    f = _font_with(top={"StrokeWidth": 0.25})
    assert f.get_stroke_width() == 0.25


def test_get_stroke_width_default_zero() -> None:
    assert _font_with().get_stroke_width() == 0.0


def test_get_stroke_width_int_coerces_to_float() -> None:
    f = _font_with(top={"StrokeWidth": 3})
    val = f.get_stroke_width()
    assert val == 3.0
    assert isinstance(val, float)


def test_get_stroke_width_garbage_returns_zero() -> None:
    f = _font_with(top={"StrokeWidth": object()})
    assert f.get_stroke_width() == 0.0


# ---------- get_font_id ----------


def test_get_font_id_returns_string() -> None:
    f = _font_with(top={"FID": "my-font-id"})
    assert f.get_font_id() == "my-font-id"


def test_get_font_id_empty_when_missing() -> None:
    assert _font_with().get_font_id() == ""


def test_get_font_id_coerces_non_string() -> None:
    f = _font_with(top={"FID": 7})
    assert f.get_font_id() == "7"


# ---------- get_blue_values / family ----------


def test_get_blue_values_returns_floats() -> None:
    f = _font_with(private={"BlueValues": [-20, 0, 800, 820]})
    assert f.get_blue_values() == [-20.0, 0.0, 800.0, 820.0]
    assert all(isinstance(v, float) for v in f.get_blue_values())


def test_get_blue_values_empty_when_no_private() -> None:
    f = _font_with()
    assert f.get_blue_values() == []


def test_get_blue_values_empty_when_missing_key() -> None:
    f = _font_with(private={})
    assert f.get_blue_values() == []


def test_get_blue_values_empty_when_no_program() -> None:
    assert Type1Font().get_blue_values() == []


def test_get_blue_values_garbage_returns_empty() -> None:
    f = _font_with(private={"BlueValues": [1, "bad", 3]})
    assert f.get_blue_values() == []


def test_get_other_blues_returns_floats() -> None:
    f = _font_with(private={"OtherBlues": [-50, -10]})
    assert f.get_other_blues() == [-50.0, -10.0]


def test_get_other_blues_default_empty() -> None:
    assert _font_with().get_other_blues() == []


def test_get_family_blues_returns_floats() -> None:
    f = _font_with(private={"FamilyBlues": [-25, 0, 750, 780]})
    assert f.get_family_blues() == [-25.0, 0.0, 750.0, 780.0]


def test_get_family_blues_default_empty() -> None:
    assert _font_with().get_family_blues() == []


def test_get_family_other_blues_returns_floats() -> None:
    f = _font_with(private={"FamilyOtherBlues": [-60, -20]})
    assert f.get_family_other_blues() == [-60.0, -20.0]


def test_get_family_other_blues_default_empty() -> None:
    assert _font_with().get_family_other_blues() == []


# ---------- blue scalar trio ----------


def test_get_blue_scale_returns_float() -> None:
    f = _font_with(private={"BlueScale": 0.0375})
    assert f.get_blue_scale() == 0.0375


def test_get_blue_scale_default_zero() -> None:
    assert _font_with().get_blue_scale() == 0.0


def test_get_blue_scale_int_coerces() -> None:
    f = _font_with(private={"BlueScale": 1})
    assert f.get_blue_scale() == 1.0


def test_get_blue_shift_returns_int() -> None:
    f = _font_with(private={"BlueShift": 7})
    assert f.get_blue_shift() == 7


def test_get_blue_shift_default_zero() -> None:
    assert _font_with().get_blue_shift() == 0


def test_get_blue_fuzz_returns_int() -> None:
    f = _font_with(private={"BlueFuzz": 1})
    assert f.get_blue_fuzz() == 1


def test_get_blue_fuzz_default_zero() -> None:
    assert _font_with().get_blue_fuzz() == 0


def test_get_blue_fuzz_garbage_returns_zero() -> None:
    f = _font_with(private={"BlueFuzz": "x"})
    assert f.get_blue_fuzz() == 0


# ---------- StdHW / StdVW / StemSnapH / StemSnapV ----------


def test_get_std_hw_returns_floats() -> None:
    f = _font_with(private={"StdHW": [70]})
    assert f.get_std_hw() == [70.0]


def test_get_std_hw_default_empty() -> None:
    assert _font_with().get_std_hw() == []


def test_get_std_vw_returns_floats() -> None:
    f = _font_with(private={"StdVW": [80]})
    assert f.get_std_vw() == [80.0]


def test_get_std_vw_default_empty() -> None:
    assert _font_with().get_std_vw() == []


def test_get_stem_snap_h_returns_floats() -> None:
    f = _font_with(private={"StemSnapH": [70, 90, 110]})
    assert f.get_stem_snap_h() == [70.0, 90.0, 110.0]


def test_get_stem_snap_h_default_empty() -> None:
    assert _font_with().get_stem_snap_h() == []


def test_get_stem_snap_v_returns_floats() -> None:
    f = _font_with(private={"StemSnapV": [80, 100, 120]})
    assert f.get_stem_snap_v() == [80.0, 100.0, 120.0]


def test_get_stem_snap_v_default_empty() -> None:
    assert _font_with().get_stem_snap_v() == []


# ---------- is_force_bold ----------


def test_is_force_bold_true() -> None:
    f = _font_with(private={"ForceBold": True})
    assert f.is_force_bold() is True


def test_is_force_bold_false() -> None:
    f = _font_with(private={"ForceBold": False})
    assert f.is_force_bold() is False


def test_is_force_bold_default_false() -> None:
    assert _font_with().is_force_bold() is False


def test_is_force_bold_string_true() -> None:
    f = _font_with(private={"ForceBold": "true"})
    assert f.is_force_bold() is True


def test_is_force_bold_string_false() -> None:
    f = _font_with(private={"ForceBold": "false"})
    assert f.is_force_bold() is False


def test_is_force_bold_empty_program() -> None:
    assert Type1Font().is_force_bold() is False


# ---------- get_language_group ----------


def test_get_language_group_returns_int() -> None:
    f = _font_with(private={"LanguageGroup": 1})
    assert f.get_language_group() == 1


def test_get_language_group_default_zero() -> None:
    assert _font_with().get_language_group() == 0


def test_get_language_group_garbage_returns_zero() -> None:
    f = _font_with(private={"LanguageGroup": None})
    assert f.get_language_group() == 0


# ---------- get_len_iv ----------


def test_get_len_iv_returns_int() -> None:
    f = _font_with(private={"lenIV": 0})
    assert f.get_len_iv() == 0


def test_get_len_iv_default_four() -> None:
    """Spec default for /lenIV when absent is 4."""
    assert _font_with().get_len_iv() == 4


def test_get_len_iv_custom() -> None:
    f = _font_with(private={"lenIV": 8})
    assert f.get_len_iv() == 8


def test_get_len_iv_garbage_falls_back() -> None:
    f = _font_with(private={"lenIV": "no"})
    assert f.get_len_iv() == 4


# ---------- Private dict shape robustness ----------


def test_private_accessors_when_private_is_not_a_dict() -> None:
    """If ``font_dict["Private"]`` is somehow not a dict the accessors
    must still return their typed defaults rather than raising."""
    f = Type1Font()
    f._t1 = _FakeT1({"FontName": "X", "Private": "not a dict"})
    assert f.get_blue_values() == []
    assert f.get_blue_scale() == 0.0
    assert f.get_blue_shift() == 0
    assert f.is_force_bold() is False
    assert f.get_language_group() == 0
    assert f.get_len_iv() == 4
