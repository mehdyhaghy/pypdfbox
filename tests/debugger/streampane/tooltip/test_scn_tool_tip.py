"""Hand-written tests for ``SCNToolTip``."""

from __future__ import annotations

from pypdfbox.debugger.streampane.tooltip import SCNToolTip
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern


class _FakePDColorSpaceRGB:
    """Stand-in color space that echoes ``value`` back as RGB."""

    def to_rgb(self, value: list[float]) -> list[float]:
        return [value[0], value[1], value[2]]


class _FakePDColorSpaceClamp:
    """Stand-in color space that returns a fixed RGB triple."""

    def __init__(self, rgb: list[float]) -> None:
        self._rgb = rgb

    def to_rgb(self, value: list[float]) -> list[float]:
        return self._rgb


class _FakeResources:
    def __init__(self, cs_by_name: dict[str, object]) -> None:
        self._cs_by_name = cs_by_name

    def get_color_space(self, name: object) -> object | None:
        return self._cs_by_name.get(name.get_name() if hasattr(name, "get_name") else str(name))


def test_scn_dispatches_through_resources() -> None:
    resources = _FakeResources({"CS0": _FakePDColorSpaceRGB()})
    payload = SCNToolTip(resources, "/CS0", "1 0 0 scn").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "ff0000"


def test_scn_strips_leading_slash() -> None:
    resources = _FakeResources({"CS1": _FakePDColorSpaceClamp([0.5, 0.5, 0.5])})
    payload = SCNToolTip(resources, "/CS1", "0.5 SCN").get_tool_tip_text()
    assert payload is not None
    assert payload.segments[0].color_hex == "808080"


def test_scn_pattern_yields_plain_text() -> None:
    pattern_cs = PDPattern()
    resources = _FakeResources({"P0": pattern_cs})
    payload = SCNToolTip(resources, "/P0", "/PatternName scn").get_tool_tip_text()
    assert payload is not None
    assert payload.plain == "Pattern"
    assert payload.segments == ()


def test_scn_missing_color_space_returns_none() -> None:
    resources = _FakeResources({})
    assert SCNToolTip(resources, "/Missing", "1 0 0 scn").get_tool_tip_text() is None


def test_scn_invalid_operands_return_none() -> None:
    resources = _FakeResources({"CS0": _FakePDColorSpaceRGB()})
    assert SCNToolTip(resources, "/CS0", "foo bar baz scn").get_tool_tip_text() is None


def test_scn_no_resources_returns_none() -> None:
    assert SCNToolTip(None, "/CS0", "1 0 0 scn").get_tool_tip_text() is None
