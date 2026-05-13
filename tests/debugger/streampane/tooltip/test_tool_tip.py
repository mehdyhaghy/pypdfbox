"""Hand-written tests for the ``ToolTip`` base + value types."""

from __future__ import annotations

from pypdfbox.debugger.streampane.tooltip import ToolTip, ToolTipSegment, ToolTipText


def test_tooltip_text_defaults() -> None:
    payload = ToolTipText()
    assert payload.plain == ""
    assert payload.segments == ()


def test_tooltip_text_round_trip() -> None:
    seg = ToolTipSegment(text="hi", color_hex="ff0000")
    payload = ToolTipText(plain="hi", segments=(seg,))
    assert payload.plain == "hi"
    assert payload.segments[0].text == "hi"
    assert payload.segments[0].color_hex == "ff0000"


def test_tooltip_segment_default_color_is_none() -> None:
    seg = ToolTipSegment(text="hello")
    assert seg.color_hex is None


def test_tooltip_is_abstract() -> None:
    # Direct instantiation of the abstract base must fail; this is the
    # Python equivalent of upstream's package-private interface.
    try:
        ToolTip()  # type: ignore[abstract]
    except TypeError:
        return
    raise AssertionError("ToolTip should be abstract")
