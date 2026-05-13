"""Hand-written tests for ``FontToolTip``."""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.debugger.streampane.tooltip import FontToolTip


class _FakeFont:
    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


class _FakeResources:
    def __init__(self, fonts: dict[str, _FakeFont]) -> None:
        self._fonts = {COSName.get_pdf_name(k): v for k, v in fonts.items()}

    def get_font_names(self) -> list[COSName]:
        return list(self._fonts.keys())

    def get_font(self, name: COSName) -> _FakeFont | None:
        return self._fonts.get(name)


def test_font_resolves_by_resource_key() -> None:
    resources = _FakeResources({"F1": _FakeFont("Helvetica")})
    payload = FontToolTip(resources, "/F1 12 Tf").get_tool_tip_text()
    assert payload is not None
    assert payload.plain == "Helvetica"
    assert payload.segments[0].text == "Helvetica"
    assert payload.segments[0].color_hex is None


def test_font_unknown_reference_returns_none() -> None:
    resources = _FakeResources({"F1": _FakeFont("Helvetica")})
    assert FontToolTip(resources, "/F9 14 Tf").get_tool_tip_text() is None


def test_font_no_resources_returns_none() -> None:
    assert FontToolTip(None, "/F1 12 Tf").get_tool_tip_text() is None


def test_font_extract_with_leading_slash() -> None:
    resources = _FakeResources({"TT0": _FakeFont("TimesNewRomanPSMT")})
    payload = FontToolTip(resources, "  /TT0 24 Tf").get_tool_tip_text()
    assert payload is not None
    assert payload.plain == "TimesNewRomanPSMT"


def test_font_extract_without_leading_slash_falls_through() -> None:
    # Defensive: upstream blindly does substring(1); we tolerate the
    # malformed token but still expect a no-match in resources.
    resources = _FakeResources({"F1": _FakeFont("Helvetica")})
    assert FontToolTip(resources, "F1 12 Tf").get_tool_tip_text() is None
