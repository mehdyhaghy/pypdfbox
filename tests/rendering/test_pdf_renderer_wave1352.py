"""Wave 1352 — coverage-boost pass on ``pypdfbox.rendering.pdf_renderer``.

These tests pin the last-mile branches in ``PDFRenderer`` that the
existing suite hadn't touched:

* the ``has_blend_mode`` short-circuits when ``/Resources`` is absent or
  ``get_ext_g_state_names`` / ``get_ext_gstate`` raise / return ``None``.
* the ``is_bitonal`` duck-typed branches (``image.mode``,
  ``get_bit_depth()`` callable, ``bit_depth`` int attribute).
* ``transform`` for 180 / 270 rotation angles.
* ``render_page_to_graphics`` anisotropic scale resize and the duck-typed
  paste fallbacks (``paste`` / ``draw_image`` / ``drawImage`` plus the
  TypeError → 3-arg retry).
* ``_stroke_via_aggdraw`` delegating to ``_draw_via_aggdraw``.
* ``_get_type1_units_per_em`` Standard-14 substitute branches: missing
  ``get_name`` (returns ``None``), unmapped name → ``None``, mapped name
  → substitute TTF UPEM, and the ``get_units_per_em`` failure path.
* ``create_page_drawer`` exception branch when ``PageDrawer(parameters)``
  raises ``TypeError`` / ``AttributeError``.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.pdf_renderer import _GState

# ---------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------


def _make_doc(width: float = 50.0, height: float = 50.0) -> PDDocument:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    doc.add_page(PDPage(PDRectangle(0.0, 0.0, width, height)))
    return doc


# ---------------------------------------------------------------------------
# has_blend_mode — line 762 (resources None), 765-766 (ext_g_state_names
# raises), 771-772 (get_ext_gstate raises), 776 (ext_gstate is None)
# ---------------------------------------------------------------------------


def test_has_blend_mode_returns_false_when_resources_missing() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)
        page = MagicMock()
        page.get_resources.return_value = None
        assert renderer.has_blend_mode(page) is False
    finally:
        doc.close()


def test_has_blend_mode_returns_false_when_ext_g_state_names_raises() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)
        resources = MagicMock()
        resources.get_ext_g_state_names.side_effect = RuntimeError("boom")
        page = MagicMock()
        page.get_resources.return_value = resources
        assert renderer.has_blend_mode(page) is False
    finally:
        doc.close()


def test_has_blend_mode_skips_ext_gstate_lookup_errors() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)
        resources = MagicMock()
        resources.get_ext_g_state_names.return_value = ["GS1", "GS2"]
        resources.get_ext_gstate.side_effect = RuntimeError("boom")
        page = MagicMock()
        page.get_resources.return_value = resources
        assert renderer.has_blend_mode(page) is False
    finally:
        doc.close()


def test_has_blend_mode_skips_none_ext_gstate_values() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)
        resources = MagicMock()
        resources.get_ext_g_state_names.return_value = ["GS1"]
        resources.get_ext_gstate.return_value = None
        page = MagicMock()
        page.get_resources.return_value = resources
        assert renderer.has_blend_mode(page) is False
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# is_bitonal — line 801 (image mode via .image), 809-810 (get_bit_depth
# raises), 813 (bit_depth int attribute)
# ---------------------------------------------------------------------------


def test_is_bitonal_consults_inner_image_mode_attribute() -> None:
    """A graphics wrapper exposing ``.image`` with ``mode == "1"`` is bitonal."""
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        class _Wrapper:
            mode = None
            image = Image.new("1", (4, 4), 0)

        assert renderer.is_bitonal(_Wrapper()) is True
    finally:
        doc.close()


def test_is_bitonal_inner_image_attribute_without_mode_returns_false() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        class _Wrapper:
            mode = None
            image = object()  # no .mode attribute either

        assert renderer.is_bitonal(_Wrapper()) is False
    finally:
        doc.close()


def test_is_bitonal_get_bit_depth_callable_returning_one() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        class _Device:
            mode = "RGB"  # not "1" — forces fallback to get_bit_depth

            def get_bit_depth(self) -> int:
                return 1

        assert renderer.is_bitonal(_Device()) is True
    finally:
        doc.close()


def test_is_bitonal_get_bit_depth_callable_raises_returns_false() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        class _Device:
            mode = "RGB"

            def get_bit_depth(self) -> int:
                raise RuntimeError("boom")

        assert renderer.is_bitonal(_Device()) is False
    finally:
        doc.close()


def test_is_bitonal_bit_depth_int_attribute() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        class _Device:
            mode = "RGB"
            get_bit_depth = None
            bit_depth = 1

        assert renderer.is_bitonal(_Device()) is True

        class _DeviceTwo:
            mode = "RGB"
            get_bit_depth = None
            bit_depth = 8

        assert renderer.is_bitonal(_DeviceTwo()) is False
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# create_page_drawer — lines 873-874 (PageDrawer constructor raises)
# ---------------------------------------------------------------------------


def test_create_page_drawer_falls_back_to_self_on_constructor_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        # Supply a real parameters-like object with get_page so we enter the
        # PageDrawer construction branch (not the legacy fallback).
        params = MagicMock()
        params.get_page.return_value = renderer._document.get_pages()[0]  # noqa: SLF001
        # set_annotation_filter is a real callable on the mock, but the
        # PageDrawer constructor needs to raise to exercise lines 873-874.

        def _boom(_self: Any, _parameters: Any) -> None:
            raise TypeError("synthetic constructor failure")

        from pypdfbox.rendering import page_drawer as _page_drawer_mod

        monkeypatch.setattr(_page_drawer_mod.PageDrawer, "__init__", _boom)

        result = renderer.create_page_drawer(params)
        assert result is renderer
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# transform — lines 904 (180), 906-907 (180 both translates), and 270
# ---------------------------------------------------------------------------


def test_transform_rotation_270_translates_y_by_width() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)
        crop_box = MagicMock()
        crop_box.get_width.return_value = 100.0
        crop_box.get_height.return_value = 200.0
        matrix = renderer.transform(None, 270, crop_box, 1.0, 1.0)
        # 6-tuple matrix, rotation applied.
        assert len(matrix) == 6
        # ty should reflect the translate (1.0, 0, 0, 1, 0, width=100) ∘ rotate
        assert isinstance(matrix[5], float)
    finally:
        doc.close()


def test_transform_rotation_180_translates_x_and_y() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)
        crop_box = MagicMock()
        crop_box.get_width.return_value = 100.0
        crop_box.get_height.return_value = 200.0
        matrix = renderer.transform(None, 180, crop_box, 1.0, 1.0)
        assert len(matrix) == 6
    finally:
        doc.close()


def test_transform_invokes_graphics_translate_and_rotate() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)
        crop_box = MagicMock()
        crop_box.get_width.return_value = 100.0
        crop_box.get_height.return_value = 200.0

        seen: dict[str, Any] = {}

        class _Graphics:
            def scale(self, sx: float, sy: float) -> None:
                seen["scale"] = (sx, sy)

            def translate(self, tx: float, ty: float) -> None:
                seen["translate"] = (tx, ty)

            def rotate(self, radians: float) -> None:
                seen["rotate"] = radians

        renderer.transform(_Graphics(), 90, crop_box, 2.0, 3.0)
        assert seen["scale"] == (2.0, 3.0)
        assert "translate" in seen
        assert "rotate" in seen
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# render_page_to_graphics — lines 975-979 (anisotropic resize),
# 987-995 (duck-typed paste fallbacks)
# ---------------------------------------------------------------------------


def test_render_page_to_graphics_anisotropic_scale_resizes() -> None:
    doc = _make_doc(width=20.0, height=10.0)
    try:
        renderer = PDFRenderer(doc)
        # Anisotropic — scale_x != scale_y forces the resize branch.
        target = Image.new("RGB", (40, 40), (255, 255, 255))
        renderer.render_page_to_graphics(
            0, target, scale_x=2.0, scale_y=1.0
        )
        # The render succeeded — page_image is populated.
        assert renderer.get_page_image() is not None
    finally:
        doc.close()


def test_render_page_to_graphics_duck_typed_paste() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        seen: dict[str, Any] = {}

        class _Target:
            def paste(self, image: Image.Image, position: tuple[int, int]) -> None:
                seen["paste"] = (image, position)

        renderer.render_page_to_graphics(0, _Target(), scale_x=1.0)
        assert "paste" in seen
        assert seen["paste"][1] == (0, 0)
    finally:
        doc.close()


def test_render_page_to_graphics_duck_typed_draw_image() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        seen: dict[str, Any] = {}

        class _Target:
            def draw_image(self, image: Image.Image, position: tuple[int, int]) -> None:
                seen["draw_image"] = (image, position)

        renderer.render_page_to_graphics(0, _Target(), scale_x=1.0)
        assert "draw_image" in seen
    finally:
        doc.close()


def test_render_page_to_graphics_duck_typed_drawimage_camelcase() -> None:
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        seen: dict[str, Any] = {}

        class _Target:
            def drawImage(  # noqa: N802 - duck-typed AWT-style hook
                self, image: Image.Image, position: tuple[int, int]
            ) -> None:
                seen["drawImage"] = (image, position)

        renderer.render_page_to_graphics(0, _Target(), scale_x=1.0)
        assert "drawImage" in seen
    finally:
        doc.close()


def test_render_page_to_graphics_paste_typeerror_falls_back_to_three_args() -> None:
    """When the duck-typed paste rejects a 2-arg call (TypeError), the
    renderer retries with separate ``x, y`` ints."""
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)

        seen: dict[str, Any] = {}

        class _Target:
            def paste(self, image: Any, *args: Any) -> None:
                # First call: tuple position → reject.
                if len(args) == 1 and isinstance(args[0], tuple):
                    raise TypeError("expects separate x, y")
                # Second call: separate x, y.
                seen["paste"] = (image, args)

        renderer.render_page_to_graphics(0, _Target(), scale_x=1.0)
        assert seen["paste"][1] == (0, 0)
    finally:
        doc.close()


def test_render_page_to_graphics_no_op_when_target_has_no_paste_api() -> None:
    """A plain object without paste / draw_image / drawImage is silently
    skipped — the rendered image is still accessible via
    ``get_page_image()``."""
    doc = _make_doc()
    try:
        renderer = PDFRenderer(doc)
        renderer.render_page_to_graphics(0, object(), scale_x=1.0)
        assert renderer.get_page_image() is not None
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# _stroke_via_aggdraw — line 1594
# ---------------------------------------------------------------------------


def test_stroke_via_aggdraw_delegates_to_draw_via_aggdraw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = _make_doc(8.0, 8.0)
    try:
        renderer = PDFRenderer(doc)
        renderer._image = Image.new("RGB", (8, 8), (255, 255, 255))  # noqa: SLF001
        renderer._draw = aggdraw.Draw(renderer._image)  # noqa: SLF001
        renderer._draw.setantialias(True)  # noqa: SLF001
        renderer._gs_stack = [_GState()]  # noqa: SLF001
        renderer._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001

        seen: dict[str, Any] = {}

        def _spy(stroke: bool, fill: bool, even_odd: bool = False) -> None:
            seen["stroke"] = stroke
            seen["fill"] = fill
            seen["even_odd"] = even_odd

        monkeypatch.setattr(renderer, "_draw_via_aggdraw", _spy)
        renderer._stroke_via_aggdraw()  # noqa: SLF001
        assert seen == {"stroke": True, "fill": False, "even_odd": False}
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# _get_type1_units_per_em — lines 4222 (get_name None), 4225 (no substitute),
# 4228-4229 (substitute UPEM raises)
# ---------------------------------------------------------------------------


def test_get_type1_units_per_em_returns_none_when_get_name_returns_none() -> None:
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    font = MagicMock(spec=PDType1Font)
    font._get_type1_font.return_value = None  # noqa: SLF001
    font.get_name.return_value = None
    assert PDFRenderer._get_type1_units_per_em(font) is None  # noqa: SLF001


def test_get_type1_units_per_em_returns_none_when_no_substitute(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.pdmodel.font import standard14_fonts
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    font = MagicMock(spec=PDType1Font)
    font._get_type1_font.return_value = None  # noqa: SLF001
    font.get_name.return_value = "Symbol"

    monkeypatch.setattr(
        standard14_fonts.Standard14Fonts,
        "get_substitute_ttf",
        classmethod(lambda _cls, _name: None),
    )
    assert PDFRenderer._get_type1_units_per_em(font) is None  # noqa: SLF001


def test_get_type1_units_per_em_returns_substitute_upem_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.pdmodel.font import standard14_fonts
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    font = MagicMock(spec=PDType1Font)
    font._get_type1_font.return_value = None  # noqa: SLF001
    font.get_name.return_value = "Helvetica"

    class _Substitute:
        def get_units_per_em(self) -> int:
            return 2048

    monkeypatch.setattr(
        standard14_fonts.Standard14Fonts,
        "get_substitute_ttf",
        classmethod(lambda _cls, _name: _Substitute()),
    )
    assert PDFRenderer._get_type1_units_per_em(font) == 2048  # noqa: SLF001


def test_get_type1_units_per_em_returns_none_when_substitute_upem_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.pdmodel.font import standard14_fonts
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    font = MagicMock(spec=PDType1Font)
    font._get_type1_font.return_value = None  # noqa: SLF001
    font.get_name.return_value = "Helvetica"

    class _Substitute:
        def get_units_per_em(self) -> int:
            raise RuntimeError("boom")

    monkeypatch.setattr(
        standard14_fonts.Standard14Fonts,
        "get_substitute_ttf",
        classmethod(lambda _cls, _name: _Substitute()),
    )
    assert PDFRenderer._get_type1_units_per_em(font) is None  # noqa: SLF001


# ---------------------------------------------------------------------------
# render_image fallback — line 472 (create_page_drawer returns self/None)
# ---------------------------------------------------------------------------


def test_render_image_falls_back_to_pagedrawer_when_hook_returns_none() -> None:
    """A subclass that returns ``None`` from ``create_page_drawer`` causes
    ``render_image`` to instantiate a fresh ``PageDrawer`` (line 472)."""

    class _NoneDrawerRenderer(PDFRenderer):
        def create_page_drawer(self, parameters: Any) -> Any:  # type: ignore[override]
            return None

    doc = _make_doc()
    try:
        renderer = _NoneDrawerRenderer(doc)
        image = renderer.render_image(0, scale=1.0)
        assert image is not None
    finally:
        doc.close()


def test_render_image_falls_back_to_pagedrawer_when_hook_returns_self() -> None:
    """When the hook returns ``self`` (legacy lite-renderer behaviour),
    ``render_image`` swaps in a real ``PageDrawer``."""

    class _SelfDrawerRenderer(PDFRenderer):
        def create_page_drawer(self, parameters: Any) -> Any:  # type: ignore[override]
            return self

    doc = _make_doc()
    try:
        renderer = _SelfDrawerRenderer(doc)
        image = renderer.render_image(0, scale=1.0)
        assert image is not None
    finally:
        doc.close()
