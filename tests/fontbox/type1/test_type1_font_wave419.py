from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font, _make_path_pen, _ParsedT1


class _FakeT1:
    def __init__(self, font: dict[str, Any]) -> None:
        self.font = font

    def __getitem__(self, key: str) -> Any:
        return self.font[key]


class _WidthOnlyCharString:
    def __init__(self, width: float) -> None:
        self.width = width
        self.draw_count = 0

    def draw(self, pen: Any) -> None:
        self.draw_count += 1


class _PathCharString:
    def __init__(self) -> None:
        self.width = 321.0

    def draw(self, pen: Any) -> None:
        pen.moveTo((1, 2))
        pen.lineTo((3, 4))
        pen.curveTo((5, 6), (7, 8), (9, 10))
        pen.closePath()


def _font_with(font_dict: dict[str, Any]) -> Type1Font:
    font = Type1Font()
    font._t1 = _FakeT1(font_dict)
    return font


def test_wave419_make_path_pen_records_all_supported_commands() -> None:
    pen = _make_path_pen()

    pen.moveTo((1, 2))
    pen.lineTo((3, 4))
    pen.curveTo((5, 6), (7, 8), (9, 10))
    pen.closePath()

    assert pen.commands == [
        ("moveto", 1.0, 2.0),
        ("lineto", 3.0, 4.0),
        ("curveto", 5.0, 6.0, 7.0, 8.0, 9.0, 10.0),
        ("closepath",),
    ]


def test_wave419_parsed_t1_exposes_mapping_surface() -> None:
    parsed = _ParsedT1({"FontName": "Wave419", "CharStrings": {"A": object()}})

    assert parsed["FontName"] == "Wave419"
    assert "CharStrings" in parsed
    assert "Encoding" not in parsed
    assert parsed.data == b""
    assert parsed.encoding == "ascii"


def test_wave419_units_per_em_uses_custom_font_matrix_scale() -> None:
    font = _font_with({"FontName": "Wave419", "FontMatrix": [0.002, 0, 0, 0.002, 0, 0]})

    assert font.font_matrix == [0.002, 0.0, 0.0, 0.002, 0.0, 0.0]
    assert font.units_per_em == 500


def test_wave419_units_per_em_zero_scale_falls_back_to_1000() -> None:
    font = _font_with({"FontName": "Wave419", "FontMatrix": [0, 0, 0, 0.001, 0, 0]})

    assert font.units_per_em == 1000


def test_wave419_encoding_vector_skips_empty_slots_and_returns_copy() -> None:
    font = _font_with({"FontName": "Wave419", "Encoding": [None, ".notdef", "A", 123]})

    encoding = font.get_encoding()
    encoding[2] = "mutated"

    assert encoding == {2: "mutated", 3: "123"}
    assert font.get_encoding() == {2: "A", 3: "123"}


def test_wave419_standard_encoding_name_resolves_to_copy() -> None:
    font = _font_with({"FontName": "Wave419", "Encoding": "StandardEncoding"})

    encoding = font.get_encoding()
    encoding[65] = "mutated"

    assert font.get_encoding()[65] == "A"


def test_wave419_charstrings_charset_empty_without_program() -> None:
    assert Type1Font().get_char_strings_subroutines_charset() == {}
    assert Type1Font().get_char_strings_dict() == {}


def test_wave419_get_width_caches_after_first_successful_draw() -> None:
    charstring = _WidthOnlyCharString(612.0)
    font = _font_with({"FontName": "Wave419", "CharStrings": {"A": charstring}})

    assert font.get_width("A") == 612.0
    assert font.get_width("A") == 612.0
    assert charstring.draw_count == 1


def test_wave419_get_path_records_outline_and_caches_width() -> None:
    charstring = _PathCharString()
    font = _font_with({"FontName": "Wave419", "CharStrings": {"A": charstring}})

    assert font.get_path("A") == [
        ("moveto", 1.0, 2.0),
        ("lineto", 3.0, 4.0),
        ("curveto", 5.0, 6.0, 7.0, 8.0, 9.0, 10.0),
        ("closepath",),
    ]
    assert font.get_width("A") == 321.0


def test_wave419_get_type1_char_string_falls_back_to_notdef() -> None:
    notdef = b""
    font = _font_with({"FontName": "Wave419", "CharStrings": {".notdef": notdef}})

    wrapper = font.get_type1_char_string("Missing")

    assert wrapper.get_name() == ".notdef"
    assert wrapper.get_font_name() == "Wave419"
