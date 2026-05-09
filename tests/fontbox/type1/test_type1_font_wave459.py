from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font


class _FakeT1:
    def __init__(self, font: dict[str, Any]) -> None:
        self.font = font

    def __getitem__(self, key: str) -> Any:
        return self.font[key]


def _font_with(font_dict: dict[str, Any]) -> Type1Font:
    font = Type1Font()
    font._t1 = _FakeT1(font_dict)
    return font


def test_wave459_metrics_bundle_uses_font_info_private_and_matrix_values() -> None:
    font = _font_with(
        {
            "FontName": "Wave459",
            "FontMatrix": [0.002, 0, 0, 0.002, 0, 0],
            "FontBBox": [-10, -20, 500, 700],
            "FontInfo": {
                "ItalicAngle": "-12.5",
                "UnderlinePosition": -75,
                "UnderlineThickness": "30",
                "isFixedPitch": True,
            },
        }
    )

    assert font.get_metrics() == {
        "FontBBox": (-10.0, -20.0, 500.0, 700.0),
        "FontMatrix": [0.002, 0.0, 0.0, 0.002, 0.0, 0.0],
        "ItalicAngle": -12.5,
        "UnderlinePosition": -75.0,
        "UnderlineThickness": 30.0,
        "UnitsPerEm": 500,
        "isFixedPitch": True,
    }
    assert font.is_italic() is True
    assert font.is_fixed_pitch() is True


def test_wave459_top_level_numeric_and_id_accessors_coerce_values() -> None:
    font = _font_with(
        {
            "FontName": "Wave459",
            "PaintType": "2",
            "FontType": 1.0,
            "UniqueID": "12345",
            "StrokeWidth": "4.5",
            "FID": 99,
        }
    )

    assert font.get_paint_type() == 2
    assert font.get_font_type() == 1
    assert font.get_unique_id() == 12345
    assert font.get_stroke_width() == 4.5
    assert font.get_font_id() == "99"


def test_wave459_bad_top_level_numeric_values_return_typed_defaults() -> None:
    font = _font_with(
        {
            "FontName": "Wave459",
            "PaintType": "bad",
            "FontType": object(),
            "UniqueID": "nope",
            "StrokeWidth": object(),
        }
    )

    assert font.get_paint_type() == 0
    assert font.get_font_type() == 0
    assert font.get_unique_id() == 0
    assert font.get_stroke_width() == 0.0
    assert font.get_font_id() == ""


def test_wave459_private_arrays_scalars_and_subrs_are_exposed_as_copies() -> None:
    subrs = [b"one", b"two"]
    font = _font_with(
        {
            "FontName": "Wave459",
            "Private": {
                "BlueValues": [1, "2.5"],
                "OtherBlues": (-3, -4),
                "FamilyBlues": [5],
                "FamilyOtherBlues": [6],
                "StdHW": [70],
                "StdVW": [80],
                "StemSnapH": [90, 91],
                "StemSnapV": [100, 101],
                "BlueScale": "0.039625",
                "BlueShift": "7",
                "BlueFuzz": 1.8,
                "ForceBold": 0,
                "LanguageGroup": "1",
                "lenIV": "2",
                "Subrs": subrs,
            },
        }
    )

    exposed = font.get_subrs_array()
    exposed.append(b"mutated")

    assert font.get_blue_values() == [1.0, 2.5]
    assert font.get_other_blues() == [-3.0, -4.0]
    assert font.get_family_blues() == [5.0]
    assert font.get_family_other_blues() == [6.0]
    assert font.get_std_hw() == [70.0]
    assert font.get_std_vw() == [80.0]
    assert font.get_stem_snap_h() == [90.0, 91.0]
    assert font.get_stem_snap_v() == [100.0, 101.0]
    assert font.get_blue_scale() == 0.039625
    assert font.get_blue_shift() == 7
    assert font.get_blue_fuzz() == 1
    assert font.is_force_bold() is False
    assert font.get_language_group() == 1
    assert font.get_len_iv() == 2
    assert font.get_subrs() == 2
    assert font.get_subrs_array() == subrs


def test_wave459_non_dict_private_and_bad_subrs_return_defaults() -> None:
    font = _font_with({"FontName": "Wave459", "Private": "not a dict"})
    bad_subrs = _font_with({"FontName": "Wave459", "Private": {"Subrs": 42}})

    assert font.get_blue_values() == []
    assert font.get_blue_scale() == 0.0
    assert font.get_blue_shift() == 0
    assert font.get_blue_fuzz() == 0
    assert font.get_len_iv() == 4
    assert font.get_subrs() == 0
    assert font.get_subrs_array() == []
    assert bad_subrs.get_subrs() == 0
    assert bad_subrs.get_subrs_array() == []


def test_wave459_type1_mappings_follow_sorted_encoding_codes() -> None:
    charstrings = {"A": b"", "space": b"", ".notdef": b""}
    font = _font_with(
        {
            "FontName": "Wave459",
            "Encoding": [None, "A", ".notdef", "space"],
            "CharStrings": charstrings,
        }
    )

    mappings = font.get_type1_mappings()

    assert [(m.get_code(), m.get_name()) for m in mappings] == [(1, "A"), (3, "space")]
    assert [m.get_type1_char_string().get_name() for m in mappings] == ["A", "space"]


def test_wave459_string_representation_includes_metadata_and_tables() -> None:
    font = _font_with(
        {
            "FontName": "Wave459",
            "FontInfo": {"FullName": "Wave 459 Test"},
            "Encoding": [".notdef", "A"],
            "CharStrings": {"A": b"chars"},
        }
    )

    text = str(font)

    assert "Type1Font[fontName=Wave459" in text
    assert "fullName=Wave 459 Test" in text
    assert "encoding={1: 'A'}" in text
    assert "charStringsDict={'A': b'chars'}" in text
