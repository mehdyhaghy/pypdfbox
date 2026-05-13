"""Hand-written tests for ``KToolTip``."""

from __future__ import annotations

from pypdfbox.debugger.streampane.tooltip import KToolTip


def test_cmyk_pure_black_via_k_channel() -> None:
    # c=m=y=0, k=1 -> the subtractive approximation yields pure black.
    payload = KToolTip("0 0 0 1 k").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "000000"


def test_cmyk_white() -> None:
    # All components zero -> white.
    payload = KToolTip("0 0 0 0 k").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "ffffff"


def test_cmyk_pure_cyan() -> None:
    # c=1, m=y=k=0 -> (1-1)(1-0)=0, (1-0)(1-0)=1, (1-0)(1-0)=1 -> #00ffff.
    payload = KToolTip("1 0 0 0 K").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "00ffff"


def test_cmyk_invalid() -> None:
    assert KToolTip("foo bar baz qux k").get_tool_tip_text() is None


def test_cmyk_too_few_components() -> None:
    assert KToolTip("1 0 0 k").get_tool_tip_text() is None
