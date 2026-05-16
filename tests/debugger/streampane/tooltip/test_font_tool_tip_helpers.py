"""Tests for the newly-promoted helpers on :class:`FontToolTip`."""

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


def test_extract_font_reference_strips_leading_slash() -> None:
    assert FontToolTip.extract_font_reference("/F1 12 Tf") == "F1"


def test_extract_font_reference_handles_extra_whitespace() -> None:
    assert FontToolTip.extract_font_reference("   /TT0  18 Tf") == "TT0"


def test_extract_font_reference_empty_returns_empty() -> None:
    assert FontToolTip.extract_font_reference("") == ""


def test_init_ui_populates_markup() -> None:
    resources = _FakeResources({"F1": _FakeFont("Helvetica")})
    tip = FontToolTip(resources, "/F1 12 Tf")
    # init_ui ran from __init__; reinvoke to confirm public surface works.
    tip._markup = None
    tip.init_ui("F1", resources)
    payload = tip.get_tool_tip_text()
    assert payload is not None
    assert payload.plain == "Helvetica"


def test_extract_alias_matches_public_method() -> None:
    assert FontToolTip._extract_font_reference is FontToolTip.extract_font_reference
    assert FontToolTip._init_ui is FontToolTip.init_ui
