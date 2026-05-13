"""Hand-written tests for ``RGToolTip``."""

from __future__ import annotations

from pypdfbox.debugger.streampane.tooltip import RGToolTip


def test_rgb_white() -> None:
    payload = RGToolTip("1 1 1 rg").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "ffffff"


def test_rgb_red_stroking() -> None:
    payload = RGToolTip("1 0 0 RG").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "ff0000"


def test_rgb_mid_gray() -> None:
    payload = RGToolTip("0.5 0.5 0.5 rg").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "808080"


def test_rgb_invalid_returns_none() -> None:
    assert RGToolTip("foo bar baz rg").get_tool_tip_text() is None


def test_rgb_too_few_components_returns_none() -> None:
    assert RGToolTip("1 0 rg").get_tool_tip_text() is None
