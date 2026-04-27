"""Extra accessor tests for ``Type1Font`` covering the methods rounded
out alongside the new parser / util modules: ``get_notice``,
``is_italic`` / ``is_fixed_pitch``, ``get_metrics``, ``get_char_string``,
``get_char_strings_dict``, and ``get_type1_mappings``.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font
from pypdfbox.fontbox.type1.type1_mapping import Type1Mapping


class _FakeT1:
    def __init__(self, font: dict[str, Any]) -> None:
        self.font = font

    def __getitem__(self, key: str) -> Any:
        return self.font[key]


def _make_font(
    *,
    font_name: str = "TestFontPS",
    font_info: dict[str, Any] | None = None,
    encoding: Any = None,
    charstrings: dict[str, Any] | None = None,
) -> Type1Font:
    fd: dict[str, Any] = {"FontName": font_name}
    if font_info is not None:
        fd["FontInfo"] = font_info
    if encoding is not None:
        fd["Encoding"] = encoding
    if charstrings is not None:
        fd["CharStrings"] = charstrings
    f = Type1Font()
    f._t1 = _FakeT1(fd)
    if charstrings is not None:
        f._charstrings = charstrings
    return f


# ---------- get_notice ----------


def test_get_notice_returns_value() -> None:
    f = _make_font(font_info={"Notice": "Copyright (c) 2024 Test"})
    assert f.get_notice() == "Copyright (c) 2024 Test"


def test_get_notice_empty_when_missing() -> None:
    f = _make_font(font_info={})
    assert f.get_notice() == ""


def test_get_notice_empty_when_no_program() -> None:
    assert Type1Font().get_notice() == ""


def test_get_notice_is_cached() -> None:
    f = _make_font(font_info={"Notice": "First"})
    assert f.get_notice() == "First"
    f._t1.font["FontInfo"]["Notice"] = "Mutated"
    assert f.get_notice() == "First"


# ---------- is_italic / is_fixed_pitch ----------


def test_is_italic_true_when_angle_nonzero() -> None:
    f = _make_font(font_info={"ItalicAngle": -12})
    assert f.is_italic() is True


def test_is_italic_false_when_angle_zero() -> None:
    f = _make_font(font_info={"ItalicAngle": 0})
    assert f.is_italic() is False


def test_is_italic_false_when_missing() -> None:
    f = _make_font(font_info={})
    assert f.is_italic() is False


def test_is_fixed_pitch_aliases_get_is_fixed_pitch() -> None:
    f = _make_font(font_info={"isFixedPitch": True})
    assert f.is_fixed_pitch() is True
    g = _make_font(font_info={"isFixedPitch": False})
    assert g.is_fixed_pitch() is False


# ---------- get_metrics ----------


def test_get_metrics_bundle_keys() -> None:
    f = _make_font(font_info={"ItalicAngle": -12, "isFixedPitch": True})
    f._t1.font["FontBBox"] = [-50, -200, 1000, 800]
    f._t1.font["FontMatrix"] = [0.001, 0, 0, 0.001, 0, 0]
    f._t1.font["FontInfo"]["UnderlinePosition"] = -100
    f._t1.font["FontInfo"]["UnderlineThickness"] = 50

    metrics = f.get_metrics()
    assert metrics["FontBBox"] == (-50.0, -200.0, 1000.0, 800.0)
    assert metrics["FontMatrix"] == [0.001, 0, 0, 0.001, 0, 0]
    assert metrics["ItalicAngle"] == -12.0
    assert metrics["UnderlinePosition"] == -100.0
    assert metrics["UnderlineThickness"] == 50.0
    assert metrics["UnitsPerEm"] == 1000
    assert metrics["isFixedPitch"] is True


def test_get_metrics_handles_missing_bbox() -> None:
    f = _make_font(font_info={})
    f._t1.font["FontMatrix"] = [0.001, 0, 0, 0.001, 0, 0]
    metrics = f.get_metrics()
    assert metrics["FontBBox"] is None
    assert metrics["UnitsPerEm"] == 1000


# ---------- get_char_string / get_char_strings_dict ----------


def test_get_char_strings_dict_returns_copy() -> None:
    cs = {".notdef": object(), "A": object(), "B": object()}
    f = _make_font(charstrings=cs)
    view = f.get_char_strings_dict()
    assert set(view.keys()) == {".notdef", "A", "B"}
    view["mutated"] = object()
    assert "mutated" not in f.get_char_strings_dict()


def test_get_char_strings_dict_aliases_subroutines_charset() -> None:
    cs = {".notdef": object(), "A": object()}
    f = _make_font(charstrings=cs)
    assert (
        f.get_char_strings_dict().keys()
        == f.get_char_strings_subroutines_charset().keys()
    )


def test_get_char_string_returns_wrapper_for_known_glyph() -> None:
    cs_obj = b"\x8b\x8b\rendchar"  # any bytes payload — Type1CharString accepts
    cs = {".notdef": b"\x8b\x8b\rendchar", "A": cs_obj}
    f = _make_font(charstrings=cs)
    wrapper = f.get_char_string("A")
    assert wrapper.get_name() == "A"


def test_get_char_string_falls_back_to_notdef() -> None:
    cs = {".notdef": b"\x8b\rendchar", "A": b"\x8b\rendchar"}
    f = _make_font(charstrings=cs)
    wrapper = f.get_char_string("Missing")
    assert wrapper.get_name() == ".notdef"


# ---------- get_type1_mappings ----------


def test_get_type1_mappings_yields_one_row_per_encoded_glyph() -> None:
    arr = [".notdef"] * 256
    arr[65] = "A"
    arr[66] = "B"
    arr[67] = "C"
    body = b"\x8b\rendchar"
    cs = {".notdef": body, "A": body, "B": body, "C": body}
    f = _make_font(encoding=arr, charstrings=cs)

    rows = f.get_type1_mappings()
    assert [m.code for m in rows] == [65, 66, 67]
    assert [m.name for m in rows] == ["A", "B", "C"]
    assert all(isinstance(m, Type1Mapping) for m in rows)


def test_get_type1_mappings_preserves_encoding_order() -> None:
    arr = [".notdef"] * 256
    arr[200] = "X"
    arr[100] = "Y"
    arr[50] = "Z"
    body = b"\x8b\rendchar"
    cs = {".notdef": body, "X": body, "Y": body, "Z": body}
    f = _make_font(encoding=arr, charstrings=cs)
    rows = f.get_type1_mappings()
    assert [m.code for m in rows] == [50, 100, 200]


def test_get_type1_mappings_empty_when_no_encoding() -> None:
    f = _make_font()
    assert f.get_type1_mappings() == []


def test_get_type1_mappings_attaches_charstring() -> None:
    arr = [".notdef"] * 256
    arr[65] = "A"
    body = b"\x8b\rendchar"
    cs = {".notdef": body, "A": body}
    f = _make_font(encoding=arr, charstrings=cs)
    rows = f.get_type1_mappings()
    assert len(rows) == 1
    assert rows[0].get_type1_char_string().get_name() == "A"
