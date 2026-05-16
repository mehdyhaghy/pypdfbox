"""Hand-written tests for the parity-tool surface methods of
``ToolTipController``: ``get_word``, ``get_row_text``, ``is_color_space``
and ``find_color_space``.

These mirror the public-named methods promoted from the upstream Java
file ``ToolTipController.java`` (lines 124-184 in PDFBox 3.0). The
semantics for ``is_color_space`` and ``find_color_space`` differ from
upstream — see ``CHANGES.md`` and the module docstring for the
parity-tool rationale.
"""

from __future__ import annotations

from pypdfbox.cos import COSName
from pypdfbox.debugger.streampane.tooltip import ToolTipController
from pypdfbox.pdmodel.graphics.color.pd_color_space import PDColorSpace
from pypdfbox.pdmodel.graphics.color.pd_device_cmyk import PDDeviceCMYK
from pypdfbox.pdmodel.graphics.color.pd_device_gray import PDDeviceGray
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_pattern import PDPattern

# ---- get_word ------------------------------------------------------------


def test_get_word_picks_token_under_caret() -> None:
    # "100 200 300 RG"; caret position 8 sits on the "0" inside "300".
    text = "100 200 300 RG"
    assert ToolTipController.get_word(text, 8) == "300"


def test_get_word_picks_first_token_at_offset_zero() -> None:
    assert ToolTipController.get_word("100 200 300 RG", 0) == "100"


def test_get_word_returns_none_on_whitespace_with_no_left_word() -> None:
    # Single space → start==end after walk, no left word → None.
    assert ToolTipController.get_word("   ", 1) is None


def test_get_word_returns_none_for_negative_offset() -> None:
    assert ToolTipController.get_word("abc", -1) is None


def test_get_word_returns_none_for_offset_past_end() -> None:
    assert ToolTipController.get_word("abc", 100) is None


def test_get_word_caret_just_after_token_rewinds() -> None:
    # Caret on the trailing space → rewinds onto the preceding word.
    text = "100 200 "
    # offset 3 == first space, char to its left is "0" of "100".
    assert ToolTipController.get_word(text, 3) == "100"


# ---- is_color_space -----------------------------------------------------


def test_is_color_space_recognises_device_rgb() -> None:
    assert ToolTipController.is_color_space("/DeviceRGB") is True


def test_is_color_space_rejects_unknown_name() -> None:
    assert ToolTipController.is_color_space("/Foo") is False


def test_is_color_space_recognises_all_eleven_canonical_names() -> None:
    expected = {
        "/DeviceGray",
        "/DeviceRGB",
        "/DeviceCMYK",
        "/Pattern",
        "/CalGray",
        "/CalRGB",
        "/Lab",
        "/ICCBased",
        "/Indexed",
        "/Separation",
        "/DeviceN",
    }
    for name in expected:
        assert ToolTipController.is_color_space(name) is True, name
    # Spot-check that nothing outside the set leaks through.
    for bogus in ("/Device", "DeviceRGB", "/devicergb", "", "/CS0"):
        assert ToolTipController.is_color_space(bogus) is False, bogus


def test_is_color_space_rejects_non_string() -> None:
    assert ToolTipController.is_color_space(None) is False  # type: ignore[arg-type]
    assert ToolTipController.is_color_space(42) is False  # type: ignore[arg-type]


# ---- find_color_space ---------------------------------------------------


def test_find_color_space_resolves_direct_device_name() -> None:
    controller = ToolTipController(None)
    cs = controller.find_color_space("/DeviceRGB")
    assert cs is PDDeviceRGB.INSTANCE
    assert isinstance(cs, PDColorSpace)


def test_find_color_space_resolves_device_gray_and_cmyk() -> None:
    controller = ToolTipController(None)
    assert controller.find_color_space("/DeviceGray") is PDDeviceGray.INSTANCE
    assert controller.find_color_space("/DeviceCMYK") is PDDeviceCMYK.INSTANCE


def test_find_color_space_resolves_pattern_name() -> None:
    controller = ToolTipController(None)
    cs = controller.find_color_space("/Pattern")
    assert isinstance(cs, PDPattern)


def test_find_color_space_resolves_resource_dict_alias() -> None:
    """When ``word`` is a resource-dict key (``/CS0``), the lookup
    goes through the supplied resources' ``/ColorSpace`` mapping.
    """

    class _StubResources:
        def __init__(self, mapping: dict[str, PDColorSpace]) -> None:
            self._mapping = mapping

        def get_color_space(
            self, name: COSName, was_default: bool = False
        ) -> PDColorSpace | None:
            return self._mapping.get(name.get_name())

        # ``PDColorSpace._create_from_cos_object`` consults this when
        # routing COSObject inputs; we never go through that branch
        # here, so a ``None`` cache is sufficient.
        def get_resource_cache(self) -> None:
            return None

    resources = _StubResources({"Foo": PDDeviceRGB.INSTANCE})
    controller = ToolTipController(None)
    cs = controller.find_color_space("/Foo", resources)
    assert cs is PDDeviceRGB.INSTANCE


def test_find_color_space_returns_none_for_unknown_alias_with_no_resources() -> None:
    controller = ToolTipController(None)
    assert controller.find_color_space("/CS0") is None


def test_find_color_space_returns_none_for_malformed_word() -> None:
    controller = ToolTipController(None)
    # Missing leading slash → not a name, returns None.
    assert controller.find_color_space("DeviceRGB") is None
    assert controller.find_color_space("") is None


def test_find_color_space_uses_bound_resources_by_default() -> None:
    """When ``resources`` is omitted, the controller falls back to its
    constructor-time resources."""

    class _StubResources:
        def __init__(self) -> None:
            self.queried: list[str] = []

        def get_color_space(
            self, name: COSName, was_default: bool = False
        ) -> PDColorSpace | None:
            self.queried.append(name.get_name())
            if name.get_name() == "MyCS":
                return PDDeviceGray.INSTANCE
            return None

        def get_resource_cache(self) -> None:
            return None

    resources = _StubResources()
    controller = ToolTipController(resources)
    assert controller.find_color_space("/MyCS") is PDDeviceGray.INSTANCE
    assert resources.queried == ["MyCS"]


# ---- get_row_text -------------------------------------------------------


def test_get_row_text_returns_line_from_string_buffer() -> None:
    text = "first\nsecond\nthird"
    assert ToolTipController.get_row_text(text, 1) == "first"
    assert ToolTipController.get_row_text(text, 2) == "second"
    assert ToolTipController.get_row_text(text, 3) == "third"


def test_get_row_text_returns_none_for_out_of_range_line() -> None:
    text = "first\nsecond"
    assert ToolTipController.get_row_text(text, 99) is None
    assert ToolTipController.get_row_text(text, 0) is None
    assert ToolTipController.get_row_text(text, -1) is None


def test_get_row_text_uses_tk_style_getter_for_text_widget_stub() -> None:
    """A widget-like object with ``get(start, end)`` returning the
    requested range stands in for ``tk.Text``."""

    class _FakeTextWidget:
        def __init__(self, lines: list[str]) -> None:
            self._lines = lines
            self.calls: list[tuple[str, str]] = []

        def get(self, start: str, end: str) -> str:
            self.calls.append((start, end))
            # Parse "N.0" / "N.end" — our stub only needs the line.
            line_no = int(start.split(".")[0])
            return self._lines[line_no - 1]

    widget = _FakeTextWidget(["alpha", "beta", "gamma"])
    assert ToolTipController.get_row_text(widget, 2) == "beta"
    assert widget.calls == [("2.0", "2.end")]


def test_get_row_text_returns_none_for_none_text_pane() -> None:
    assert ToolTipController.get_row_text(None, 1) is None


def test_get_row_text_returns_none_for_unsupported_text_pane() -> None:
    class _NoGet:
        pass

    assert ToolTipController.get_row_text(_NoGet(), 1) is None
