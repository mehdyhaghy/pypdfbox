"""Additional accessor tests for ``Type1Font`` covering the wave of
upstream getters added alongside this round-out:
``get_font_name`` / ``get_font_matrix`` / ``get_version`` /
``get_paint_type`` / ``get_font_type`` / ``get_subrs_array`` /
``get_ascii_segment`` / ``get_binary_segment`` and ``__str__``.

Pattern matches ``test_type1_font_extras.py``: hand-roll a parsed font
dict and inject it via ``_t1`` so we exercise the accessor surface
without depending on a binary fixture.
"""

from __future__ import annotations

from typing import Any

from pypdfbox.fontbox.type1.type1_font import Type1Font


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
    subrs: Any = None,
    paint_type: Any = None,
    font_type: Any = None,
    font_matrix: list[float] | None = None,
) -> Type1Font:
    fd: dict[str, Any] = {"FontName": font_name}
    if font_info is not None:
        fd["FontInfo"] = font_info
    if encoding is not None:
        fd["Encoding"] = encoding
    if charstrings is not None:
        fd["CharStrings"] = charstrings
    if subrs is not None:
        fd["Private"] = {"Subrs": subrs}
    if paint_type is not None:
        fd["PaintType"] = paint_type
    if font_type is not None:
        fd["FontType"] = font_type
    if font_matrix is not None:
        fd["FontMatrix"] = font_matrix
    f = Type1Font()
    f._t1 = _FakeT1(fd)
    if charstrings is not None:
        f._charstrings = charstrings
    return f


# ---------- get_font_name ----------


def test_get_font_name_aliases_get_name() -> None:
    f = _make_font(font_name="Helvetica")
    assert f.get_font_name() == "Helvetica"
    assert f.get_font_name() == f.get_name()


def test_get_font_name_empty_when_no_program() -> None:
    assert Type1Font().get_font_name() == ""


# ---------- get_font_matrix ----------


def test_get_font_matrix_returns_list() -> None:
    f = _make_font(font_matrix=[0.001, 0, 0, 0.001, 0, 0])
    assert f.get_font_matrix() == [0.001, 0, 0, 0.001, 0, 0]


def test_get_font_matrix_returns_fresh_list_each_call() -> None:
    f = _make_font(font_matrix=[0.001, 0, 0, 0.001, 0, 0])
    a = f.get_font_matrix()
    b = f.get_font_matrix()
    a.append(99)
    # Mutating one return value must not leak into the next call.
    assert 99 not in f.get_font_matrix()
    assert b == [0.001, 0, 0, 0.001, 0, 0]


# ---------- get_version ----------


def test_get_version_lowercase_key() -> None:
    f = _make_font(font_info={"version": "001.007"})
    assert f.get_version() == "001.007"


def test_get_version_uppercase_fallback() -> None:
    f = _make_font(font_info={"Version": "2.0"})
    assert f.get_version() == "2.0"


def test_get_version_empty_when_missing() -> None:
    f = _make_font(font_info={})
    assert f.get_version() == ""


def test_get_version_empty_when_no_program() -> None:
    assert Type1Font().get_version() == ""


def test_get_version_is_cached() -> None:
    f = _make_font(font_info={"version": "1"})
    assert f.get_version() == "1"
    f._t1.font["FontInfo"]["version"] = "mutated"
    assert f.get_version() == "1"


# ---------- get_paint_type ----------


def test_get_paint_type_default_zero() -> None:
    f = _make_font()
    assert f.get_paint_type() == 0


def test_get_paint_type_returns_value() -> None:
    f = _make_font(paint_type=2)
    assert f.get_paint_type() == 2


def test_get_paint_type_garbage_returns_zero() -> None:
    f = _make_font(paint_type="not-a-number")
    assert f.get_paint_type() == 0


# ---------- get_font_type ----------


def test_get_font_type_default_zero() -> None:
    f = _make_font()
    assert f.get_font_type() == 0


def test_get_font_type_returns_value() -> None:
    f = _make_font(font_type=1)
    assert f.get_font_type() == 1


# ---------- get_subrs_array ----------


def test_get_subrs_array_returns_list() -> None:
    items = [b"x", b"y", b"z"]
    f = _make_font(subrs=items)
    arr = f.get_subrs_array()
    assert arr == items
    # Distinct list — mutating must not affect the underlying program.
    arr.append(b"w")
    assert f.get_subrs_array() == items


def test_get_subrs_array_empty_when_missing() -> None:
    assert _make_font().get_subrs_array() == []


def test_get_subrs_array_empty_when_no_program() -> None:
    assert Type1Font().get_subrs_array() == []


def test_get_subrs_array_handles_non_iterable() -> None:
    f = _make_font(subrs=42)
    assert f.get_subrs_array() == []


def test_get_subrs_array_count_matches_get_subrs() -> None:
    f = _make_font(subrs=[b"a", b"b", b"c"])
    assert len(f.get_subrs_array()) == f.get_subrs()


# ---------- get_ascii_segment / get_binary_segment ----------


def test_get_ascii_segment_returns_segment1() -> None:
    f = Type1Font()
    f._segment1 = b"%!PS-AdobeFont-1.0\nheader bytes"
    assert f.get_ascii_segment() == b"%!PS-AdobeFont-1.0\nheader bytes"


def test_get_binary_segment_returns_segment2() -> None:
    f = Type1Font()
    f._segment2 = b"\x01\x02\x03encryptedbytes"
    assert f.get_binary_segment() == b"\x01\x02\x03encryptedbytes"


def test_segments_default_empty() -> None:
    f = Type1Font()
    assert f.get_ascii_segment() == b""
    assert f.get_binary_segment() == b""


# ---------- __str__ ----------


def test_str_contains_font_name_and_full_name() -> None:
    f = _make_font(
        font_name="MyFont",
        font_info={"FullName": "My Font Regular"},
    )
    s = str(f)
    assert "fontName=MyFont" in s
    assert "fullName=My Font Regular" in s
    assert "Type1Font" in s


def test_str_does_not_raise_when_empty() -> None:
    # Plain Type1Font with no program attached still renders.
    s = str(Type1Font())
    assert "fontName=" in s
    assert "encoding=" in s
