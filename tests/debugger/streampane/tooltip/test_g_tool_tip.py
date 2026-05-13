"""Hand-written tests for ``GToolTip``."""

from __future__ import annotations

from pypdfbox.debugger.streampane.tooltip import GToolTip


def test_gray_black() -> None:
    payload = GToolTip("0 g").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "000000"


def test_gray_white_stroking() -> None:
    payload = GToolTip("1 G").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "ffffff"


def test_gray_mid() -> None:
    payload = GToolTip("0.5 g").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "808080"


def test_gray_invalid() -> None:
    assert GToolTip("nope g").get_tool_tip_text() is None


def test_gray_empty_components() -> None:
    assert GToolTip("g").get_tool_tip_text() is None
