"""Hand-written tests for ``ToolTipController``."""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.debugger.streampane.tooltip import ToolTipController


class _FakeFont:
    def __init__(self, name: str) -> None:
        self._name = name

    def get_name(self) -> str:
        return self._name


class _FakeColorSpace:
    def to_rgb(self, value: list[float]) -> list[float]:
        return [value[0], value[1], value[2]]


class _FakeResources:
    def __init__(
        self,
        fonts: dict[str, _FakeFont] | None = None,
        color_spaces: dict[str, _FakeColorSpace] | None = None,
    ) -> None:
        self._fonts = {COSName.get_pdf_name(k): v for k, v in (fonts or {}).items()}
        self._color_spaces = (color_spaces or {})

    def get_font_names(self) -> list[COSName]:
        return list(self._fonts.keys())

    def get_font(self, name: COSName) -> _FakeFont | None:
        return self._fonts.get(name)

    def get_color_space(self, name: COSName) -> object | None:
        return self._color_spaces.get(name.get_name())


# ---- get_words ------------------------------------------------------------


def test_get_words_simple() -> None:
    assert ToolTipController.get_words("1 0 0 rg") == ["1", "0", "0", "rg"]


def test_get_words_strips_empties_and_newlines() -> None:
    assert ToolTipController.get_words("  1   2  \n") == ["1", "2"]


# ---- rg dispatch ----------------------------------------------------------


def test_dispatch_rg_returns_swatch() -> None:
    text = "1 0 0 rg\n"
    controller = ToolTipController(None)
    # Caret on the "rg" token (offset within the word "rg").
    payload = controller.get_tool_tip(text.index("rg"), text)
    assert payload is not None
    assert payload.segments[0].color_hex == "ff0000"


def test_dispatch_rg_stroking_uppercase() -> None:
    text = "0 1 0 RG\n"
    controller = ToolTipController(None)
    payload = controller.get_tool_tip(text.index("RG"), text)
    assert payload is not None
    assert payload.segments[0].color_hex == "00ff00"


# ---- g / k dispatch -------------------------------------------------------


def test_dispatch_g() -> None:
    text = "0.5 g\n"
    controller = ToolTipController(None)
    payload = controller.get_tool_tip(text.index("g"), text)
    assert payload is not None
    assert payload.segments[0].color_hex == "808080"


def test_dispatch_k_uses_subtractive_cmyk() -> None:
    text = "0 0 0 1 k\n"
    controller = ToolTipController(None)
    payload = controller.get_tool_tip(text.index("k"), text)
    assert payload is not None
    assert payload.segments[0].color_hex == "000000"


# ---- Tf dispatch ----------------------------------------------------------


def test_dispatch_tf_resolves_font_name() -> None:
    resources = _FakeResources(fonts={"F1": _FakeFont("Helvetica")})
    text = "/F1 12 Tf\n"
    controller = ToolTipController(resources)
    payload = controller.get_tool_tip(text.index("Tf"), text)
    assert payload is not None
    assert payload.plain == "Helvetica"


# ---- scn / SCN dispatch ---------------------------------------------------


def test_dispatch_scn_walks_upwards_for_colorspace() -> None:
    resources = _FakeResources(color_spaces={"CS0": _FakeColorSpace()})
    text = "/CS0 cs\n1 0 0 scn\n"
    controller = ToolTipController(resources)
    payload = controller.get_tool_tip(text.index("scn"), text)
    assert payload is not None
    assert payload.segments[0].color_hex == "ff0000"


def test_dispatch_scn_uppercase_uses_uppercase_cs() -> None:
    resources = _FakeResources(color_spaces={"CS1": _FakeColorSpace()})
    text = "/CS1 CS\n0 1 0 SCN\n"
    controller = ToolTipController(resources)
    payload = controller.get_tool_tip(text.index("SCN"), text)
    assert payload is not None
    assert payload.segments[0].color_hex == "00ff00"


def test_dispatch_scn_without_cs_row_returns_none() -> None:
    resources = _FakeResources(color_spaces={"CS0": _FakeColorSpace()})
    text = "1 0 0 scn\n"
    controller = ToolTipController(resources)
    assert controller.get_tool_tip(text.index("scn"), text) is None


# ---- non-operator words ---------------------------------------------------


def test_unknown_operator_returns_none() -> None:
    text = "1 0 0 0 z\n"
    controller = ToolTipController(None)
    assert controller.get_tool_tip(text.index("z"), text) is None


def test_caret_on_whitespace_returns_none() -> None:
    text = "1 0 0 rg\n"
    controller = ToolTipController(None)
    assert controller.get_tool_tip(1, text) is None  # the first space


# ---- text-component adapter ----------------------------------------------


def test_text_component_adapter_accepts_get_method() -> None:
    class _Buffer:
        def __init__(self, content: str) -> None:
            self._content = content

        def get(self, start: str, end: str) -> str:  # noqa: ARG002
            return self._content

    controller = ToolTipController(None)
    buffer = _Buffer("1 0 0 rg\n")
    payload = controller.get_tool_tip(6, buffer)  # caret on "rg"
    assert payload is not None
    assert payload.segments[0].color_hex == "ff0000"


def test_none_text_component_returns_none() -> None:
    controller = ToolTipController(None)
    assert controller.get_tool_tip(0, None) is None
