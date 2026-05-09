from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font


class _FakeT1:
    def __init__(self, font: Any) -> None:
        self.font = font

    def __getitem__(self, key: str) -> Any:
        return self.font[key]


class _ExplodingCharString:
    def draw(self, pen: Any) -> None:
        raise ValueError("bad charstring")


def _font_with(font_dict: dict[str, Any]) -> Type1Font:
    font = Type1Font()
    font._t1 = _FakeT1(font_dict)
    return font


def test_wave374_font_dict_ignores_non_dict_font_attribute() -> None:
    font = Type1Font()
    font._t1 = _FakeT1(["not", "a", "dict"])

    assert font.get_name() == ""
    assert font.get_encoding() == {}
    assert font.get_len_iv() == 4


def test_wave374_name_falls_back_to_font_info_font_name() -> None:
    font = _font_with({"FontInfo": {"FontName": "InfoOnlyName"}})

    assert font.get_name() == "InfoOnlyName"
    assert font.get_font_name() == "InfoOnlyName"


def test_wave374_font_info_accessors_ignore_non_dict_font_info() -> None:
    font = _font_with({"FontName": "Wave374", "FontInfo": "not a dict"})

    assert font.get_full_name() == ""
    assert font.get_family_name() == ""
    assert font.get_italic_angle() == 0.0
    assert font.get_is_fixed_pitch() is False


def test_wave374_font_bbox_returns_none_for_bad_shapes() -> None:
    assert _font_with({"FontName": "Wave374", "FontBBox": [0, 1, 2]}).get_font_bbox() is None
    assert (
        _font_with({"FontName": "Wave374", "FontBBox": [0, "bad", 2, 3]}).get_font_bbox()
        is None
    )
    assert _font_with({"FontName": "Wave374", "FontBBox": object()}).get_font_bbox() is None


def test_wave374_encoding_unknown_name_returns_empty() -> None:
    assert _font_with({"FontName": "Wave374", "Encoding": "MysteryEncoding"}).get_encoding() == {}


def test_wave374_encoding_non_iterable_falls_back_to_standard_encoding() -> None:
    encoding = _font_with({"FontName": "Wave374", "Encoding": 42}).get_encoding()

    assert encoding[32] == "space"
    assert encoding[65] == "A"


def test_wave374_encoding_all_notdef_falls_back_to_standard_encoding() -> None:
    font = _font_with({"FontName": "Wave374", "Encoding": [".notdef"] * 256})

    encoding = font.get_encoding()

    assert encoding[32] == "space"
    assert encoding[65] == "A"


def test_wave374_private_accessors_handle_non_iterable_arrays_and_string_bools() -> None:
    font = _font_with(
        {
            "FontName": "Wave374",
            "Private": {
                "BlueValues": 42,
                "StdHW": ["bad"],
                "ForceBold": " TRUE ",
                "BlueScale": "no",
            },
        }
    )

    assert font.get_blue_values() == []
    assert font.get_std_hw() == []
    assert font.is_force_bold() is True
    assert font.get_blue_scale() == 0.0


def test_wave374_has_glyph_false_without_program() -> None:
    assert Type1Font().has_glyph("A") is False


def test_wave374_get_width_and_path_swallow_charstring_draw_errors() -> None:
    bad = _ExplodingCharString()
    font = _font_with({"FontName": "Wave374", "CharStrings": {"A": bad}})

    assert font.get_width("A") == 0.0
    assert font.get_path("A") == []


def test_wave374_type1_char_string_empty_wrapper_without_program() -> None:
    wrapper = Type1Font().get_type1_char_string("A")

    assert wrapper.get_name() == "A"
    assert wrapper.get_path() == []
