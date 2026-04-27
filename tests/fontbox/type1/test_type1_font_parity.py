"""Parity tests for the FontInfo / metadata accessors on
:class:`pypdfbox.fontbox.type1.type1_font.Type1Font`.

Mirrors the upstream ``org.apache.fontbox.type1.Type1Font`` getter
surface (``getName`` / ``getFamilyName`` / ``getFullName`` / ``getWeight``
/ ``getItalicAngle`` / ``getIsFixedPitch`` / ``getUnderlinePosition`` /
``getUnderlineThickness`` / ``getFontBBox`` / ``getEncoding`` /
``getCharStringsSubroutinesCharset`` / ``getSubrs``).

Generating valid PFA/PFB Type 1 bytes from scratch is fragile because
fontTools' tiny PostScript interpreter has known limitations around the
``256 array … put`` initialisation pattern that real fonts use. The
existing fontbox tests follow the "inject the parsed font dict by hand"
pattern (see ``tests/pdmodel/font/test_type1_cff_glyph.py``); we reuse
that pattern here so the accessor surface is exercised against a
realistic font dict shape without depending on a binary fixture.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.encoding.standard_encoding import StandardEncoding
from pypdfbox.fontbox.type1.type1_font import Type1Font


# ---------- helpers ----------


class _FakeT1:
    """Minimal stand-in for fontTools' ``T1Font``. Only the ``.font``
    attribute is consulted by the accessors under test."""

    def __init__(self, font: dict[str, Any]) -> None:
        self.font = font


def _make_font(
    *,
    font_name: str = "TestFontPS",
    font_info: dict[str, Any] | None = None,
    font_bbox: list[float] | None = None,
    encoding: Any = None,
    subrs: list[bytes] | None = None,
    charstrings: dict[str, Any] | None = None,
) -> Type1Font:
    """Build a Type1Font instance with a hand-rolled parsed font dict."""
    font_dict: dict[str, Any] = {"FontName": font_name}
    if font_info is not None:
        font_dict["FontInfo"] = font_info
    if font_bbox is not None:
        font_dict["FontBBox"] = font_bbox
    if encoding is not None:
        font_dict["Encoding"] = encoding
    if subrs is not None:
        font_dict["Private"] = {"Subrs": subrs}
    if charstrings is not None:
        font_dict["CharStrings"] = charstrings

    program = Type1Font()
    program._t1 = _FakeT1(font_dict)
    if charstrings is not None:
        program._charstrings = charstrings
    return program


def _full_font_info() -> dict[str, Any]:
    return {
        "version": "001.000",
        "FullName": "Test Font Regular",
        "FamilyName": "TestFont",
        "Weight": "Bold",
        "ItalicAngle": -12,
        "isFixedPitch": True,
        "UnderlinePosition": -100,
        "UnderlineThickness": 50,
    }


# ---------- get_name / get_family_name / get_full_name / get_weight ----------


def test_get_name_returns_top_level_font_name() -> None:
    font = _make_font(font_name="MyType1PS", font_info=_full_font_info())
    assert font.get_name() == "MyType1PS"


def test_get_family_name_from_font_info() -> None:
    font = _make_font(font_info=_full_font_info())
    assert font.get_family_name() == "TestFont"


def test_get_full_name_from_font_info() -> None:
    font = _make_font(font_info=_full_font_info())
    assert font.get_full_name() == "Test Font Regular"


def test_get_weight_from_font_info() -> None:
    font = _make_font(font_info=_full_font_info())
    assert font.get_weight() == "Bold"


def test_round_trip_name_family_weight_with_minimal_font_info() -> None:
    """Round-trip the three most commonly needed metadata fields
    against a minimal but realistic font_info dict."""
    info = {"FullName": "Helvetica", "FamilyName": "Helvetica", "Weight": "Roman"}
    font = _make_font(font_name="Helvetica", font_info=info)
    assert font.get_name() == "Helvetica"
    assert font.get_family_name() == "Helvetica"
    assert font.get_full_name() == "Helvetica"
    assert font.get_weight() == "Roman"


def test_get_name_falls_back_to_font_info_font_name() -> None:
    """Some fonts only carry /FontName inside /FontInfo (rare). The
    accessor should still surface it."""
    program = Type1Font()
    program._t1 = _FakeT1({"FontInfo": {"FontName": "FromInfo"}})
    assert program.get_name() == "FromInfo"


def test_string_accessors_return_empty_when_missing() -> None:
    font = _make_font(font_info={})
    assert font.get_family_name() == ""
    assert font.get_full_name() == ""
    assert font.get_weight() == ""


def test_get_name_empty_when_no_font_dict() -> None:
    """A bare Type1Font (no fontTools attached) returns the empty
    string instead of raising — matches Java's null-tolerant getters."""
    program = Type1Font()
    assert program.get_name() == ""
    assert program.get_family_name() == ""
    assert program.get_full_name() == ""
    assert program.get_weight() == ""


def test_string_accessors_are_cached() -> None:
    font = _make_font(font_info=_full_font_info())
    # First call populates the cache; second call must reuse it even
    # when we mutate the underlying font dict in between.
    assert font.get_family_name() == "TestFont"
    font._t1.font["FontInfo"]["FamilyName"] = "Mutated"
    assert font.get_family_name() == "TestFont"


# ---------- get_italic_angle ----------


def test_get_italic_angle_returns_float() -> None:
    font = _make_font(font_info=_full_font_info())
    angle = font.get_italic_angle()
    assert isinstance(angle, float)
    assert angle == -12.0


def test_get_italic_angle_default_zero() -> None:
    font = _make_font(font_info={})
    assert font.get_italic_angle() == 0.0


def test_get_italic_angle_handles_string_value() -> None:
    font = _make_font(font_info={"ItalicAngle": "-7.5"})
    assert font.get_italic_angle() == -7.5


def test_get_italic_angle_returns_zero_for_garbage() -> None:
    font = _make_font(font_info={"ItalicAngle": "notanumber"})
    assert font.get_italic_angle() == 0.0


# ---------- get_is_fixed_pitch ----------


def test_get_is_fixed_pitch_true() -> None:
    font = _make_font(font_info={"isFixedPitch": True})
    assert font.get_is_fixed_pitch() is True


def test_get_is_fixed_pitch_false() -> None:
    font = _make_font(font_info={"isFixedPitch": False})
    assert font.get_is_fixed_pitch() is False


def test_get_is_fixed_pitch_default_false() -> None:
    font = _make_font(font_info={})
    assert font.get_is_fixed_pitch() is False


def test_get_is_fixed_pitch_accepts_string_true() -> None:
    font = _make_font(font_info={"isFixedPitch": "true"})
    assert font.get_is_fixed_pitch() is True


def test_get_is_fixed_pitch_string_false() -> None:
    font = _make_font(font_info={"isFixedPitch": "false"})
    assert font.get_is_fixed_pitch() is False


# ---------- get_underline_position / get_underline_thickness ----------


def test_get_underline_position() -> None:
    font = _make_font(font_info=_full_font_info())
    assert font.get_underline_position() == -100.0


def test_get_underline_thickness() -> None:
    font = _make_font(font_info=_full_font_info())
    assert font.get_underline_thickness() == 50.0


def test_underline_metrics_default_zero() -> None:
    font = _make_font(font_info={})
    assert font.get_underline_position() == 0.0
    assert font.get_underline_thickness() == 0.0


def test_underline_metrics_handle_string_input() -> None:
    font = _make_font(
        font_info={"UnderlinePosition": "-50.5", "UnderlineThickness": "25"}
    )
    assert font.get_underline_position() == -50.5
    assert font.get_underline_thickness() == 25.0


# ---------- get_font_bbox ----------


def test_get_font_bbox_returns_four_tuple() -> None:
    font = _make_font(font_bbox=[-50, -200, 1000, 800])
    bbox = font.get_font_bbox()
    assert bbox == (-50.0, -200.0, 1000.0, 800.0)
    # Element types are floats, not the input ints.
    assert all(isinstance(v, float) for v in bbox)  # type: ignore[union-attr]


def test_get_font_bbox_none_when_missing() -> None:
    font = _make_font()
    assert font.get_font_bbox() is None


def test_get_font_bbox_none_when_wrong_length() -> None:
    font = _make_font(font_bbox=[0.0, 1.0, 2.0])
    assert font.get_font_bbox() is None


def test_get_font_bbox_none_when_non_numeric() -> None:
    font = _make_font(font_bbox=["a", "b", "c", "d"])  # type: ignore[arg-type]
    assert font.get_font_bbox() is None


# ---------- get_encoding ----------


def test_get_encoding_array_skips_notdef_slots() -> None:
    arr = [".notdef"] * 256
    arr[65] = "A"
    arr[66] = "B"
    font = _make_font(encoding=arr)
    enc = font.get_encoding()
    assert enc[65] == "A"
    assert enc[66] == "B"
    assert 64 not in enc  # default .notdef → omitted


def test_get_encoding_returns_copy() -> None:
    arr = [".notdef"] * 256
    arr[65] = "A"
    font = _make_font(encoding=arr)
    enc = font.get_encoding()
    enc[100] = "mutated"
    # Re-fetching should not see the mutation.
    assert 100 not in font.get_encoding()


def test_get_encoding_named_standard_encoding() -> None:
    font = _make_font(encoding="StandardEncoding")
    enc = font.get_encoding()
    expected = StandardEncoding.INSTANCE.get_codes()
    assert enc == expected


def test_get_encoding_empty_when_missing() -> None:
    font = _make_font()
    assert font.get_encoding() == {}


def test_get_encoding_falls_back_to_standard_when_array_all_notdef() -> None:
    """Real-world Type 1 fonts that present an Encoding array of all
    ``.notdef`` entries are interpreted as relying on StandardEncoding."""
    arr = [".notdef"] * 256
    font = _make_font(encoding=arr)
    enc = font.get_encoding()
    assert enc == StandardEncoding.INSTANCE.get_codes()


# ---------- get_char_strings_subroutines_charset ----------


def test_get_char_strings_subroutines_charset_returns_glyph_keys() -> None:
    cs_map = {".notdef": object(), "A": object(), "B": object()}
    font = _make_font(charstrings=cs_map)
    view = font.get_char_strings_subroutines_charset()
    assert set(view.keys()) == {".notdef", "A", "B"}


def test_get_char_strings_subroutines_charset_returns_copy() -> None:
    cs_map = {".notdef": object(), "A": object()}
    font = _make_font(charstrings=cs_map)
    view = font.get_char_strings_subroutines_charset()
    view["mutated"] = object()
    # Underlying charstrings must remain untouched.
    assert "mutated" not in font.get_char_strings_subroutines_charset()


def test_get_char_strings_subroutines_charset_empty_when_no_program() -> None:
    program = Type1Font()
    assert program.get_char_strings_subroutines_charset() == {}


# ---------- get_subrs ----------


def test_get_subrs_counts_array_length() -> None:
    font = _make_font(subrs=[b"x", b"y", b"z", b"w"])
    assert font.get_subrs() == 4


def test_get_subrs_zero_when_array_empty() -> None:
    font = _make_font(subrs=[])
    assert font.get_subrs() == 0


def test_get_subrs_zero_when_missing() -> None:
    font = _make_font()
    assert font.get_subrs() == 0


def test_get_subrs_zero_when_not_a_collection() -> None:
    program = Type1Font()
    program._t1 = _FakeT1({"Private": {"Subrs": 42}})
    assert program.get_subrs() == 0
