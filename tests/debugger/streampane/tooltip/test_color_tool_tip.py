"""Hand-written tests for ``ColorToolTip`` helpers."""

from __future__ import annotations

from pypdfbox.debugger.streampane.tooltip import ColorToolTip


class _Concrete(ColorToolTip):
    """A trivial concrete subclass used purely to exercise the helpers."""


def test_color_hex_value_white() -> None:
    assert ColorToolTip.color_hex_value((1.0, 1.0, 1.0)) == "ffffff"


def test_color_hex_value_black() -> None:
    assert ColorToolTip.color_hex_value((0.0, 0.0, 0.0)) == "000000"


def test_color_hex_value_red() -> None:
    assert ColorToolTip.color_hex_value((1.0, 0.0, 0.0)) == "ff0000"


def test_color_hex_value_clamps_out_of_range() -> None:
    # ICC / CMYK paths can yield channels just outside [0, 1] — the
    # upstream Color constructor would throw; the port clamps quietly.
    assert ColorToolTip.color_hex_value((-0.1, 0.5, 1.2)) == "0080ff"


def test_extract_color_values_rgb() -> None:
    assert ColorToolTip.extract_color_values("1.0 0.5 0.0 rg") == [1.0, 0.5, 0.0]


def test_extract_color_values_cmyk() -> None:
    assert ColorToolTip.extract_color_values("0.0 0.0 0.0 1.0 K") == [0.0, 0.0, 0.0, 1.0]


def test_extract_color_values_non_numeric_returns_none() -> None:
    assert ColorToolTip.extract_color_values("foo bar baz rg") is None


def test_extract_color_values_handles_leading_whitespace() -> None:
    assert ColorToolTip.extract_color_values("   0.25 0.75 0.5 rg") == [0.25, 0.75, 0.5]


def test_get_markup_returns_swatch_segment() -> None:
    ctt = _Concrete()
    payload = ctt.get_markup("12ab34")
    assert payload.plain == "#12ab34"
    assert len(payload.segments) == 1
    assert payload.segments[0].color_hex == "12ab34"


def test_set_and_get_tool_tip_text() -> None:
    ctt = _Concrete()
    assert ctt.get_tool_tip_text() is None
    ctt.set_tool_tip_text(ctt.get_markup("aabbcc"))
    payload = ctt.get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "aabbcc"
