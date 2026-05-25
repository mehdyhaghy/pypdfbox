"""Wave 1397 branch-coverage tests for ``PageDrawer``.

Closes False-branch arrows where the drawer probes the underlying
renderer for an optional helper and exits cleanly when missing:

* ``set_rendering_hints`` 178->exit — hints already initialised: skip lazy
* ``draw_image`` 334->exit — renderer lacks ``_paste_image``
* ``shading_fill`` 358->exit — renderer lacks ``_paint_shading``
* ``show_annotation`` 373->exit — renderer lacks ``_render_annotation``
* ``show_font_glyph`` 428->exit — renderer lacks ``_render_glyph``
* ``show_transparency_group`` / fallback 582->590 — graphics arg is
  not a PIL Image: skip the rebinding branch
* ``begin_text_clip`` 611->exit — ``_text_clippings`` is already a list
* ``end_text_clip`` 619->exit — ``_text_clippings`` is empty/None
* ``draw_glyph`` 625->exit — renderer lacks ``_draw_glyph_path``
* ``draw_tiling_pattern`` 633->exit — renderer lacks ``_paint_tiling_pattern``
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PageDrawerParameters, PDFRenderer, RenderDestination
from pypdfbox.rendering.page_drawer import PageDrawer


def _drawer_with_bare_renderer() -> tuple[PageDrawer, PDFRenderer]:
    """Build a PageDrawer over a renderer stripped of optional helpers
    so the ``callable(helper)`` guards all evaluate False."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    doc.add_page(page)
    renderer = PDFRenderer(doc)
    # Replace any optional helpers with a non-callable sentinel so the
    # ``callable(helper)`` guards all evaluate False. We don't try to
    # delete (some attrs are class-level methods, not instance dict).
    for attr in (
        "_paste_image",
        "_paint_shading",
        "_render_annotation",
        "_render_glyph",
        "_draw_glyph_path",
        "_paint_tiling_pattern",
        "_render_form_xobject",
    ):
        setattr(renderer, attr, None)
    renderer._image = Image.new("RGB", (100, 100), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw  # noqa: PLC0415

    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._draw.setantialias(True)
    renderer._scale = 1.0
    from pypdfbox.rendering.pdf_renderer import _GState

    renderer._gs_stack = [_GState()]
    renderer._resources = None
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.EXPORT,
        rendering_hints=None,
        image_downscaling_optimization_threshold=0.0,
    )
    return PageDrawer(params), renderer


def test_set_rendering_hints_idempotent_when_already_initialised() -> None:
    """Closes 178->exit: a non-None ``_rendering_hints`` skips the
    lazy assignment branch."""
    drawer, _ = _drawer_with_bare_renderer()
    sentinel = object()
    drawer._rendering_hints = sentinel  # type: ignore[assignment]  # noqa: SLF001
    drawer.set_rendering_hints()
    # The sentinel survived; no fresh hints were materialised.
    assert drawer._rendering_hints is sentinel  # noqa: SLF001


def test_draw_image_exits_when_renderer_lacks_paste_image_helper() -> None:
    """Closes 334->exit: a renderer without ``_paste_image`` is a no-op."""
    drawer, _ = _drawer_with_bare_renderer()

    class _Img:
        def get_image(self) -> Any:
            return Image.new("RGB", (10, 10), (0, 0, 0))

    # Should not raise.
    drawer.draw_image(_Img())


def test_shading_fill_exits_when_renderer_lacks_paint_shading() -> None:
    """Closes 358->exit: renderer without ``_paint_shading`` is a no-op."""
    drawer, rdr = _drawer_with_bare_renderer()

    class _Resources:
        def get_shading(self, name: Any) -> object:
            return object()

    rdr._resources = _Resources()
    drawer.shading_fill(COSName.get_pdf_name("Sh1"))


def test_show_annotation_exits_when_renderer_lacks_render_annotation() -> None:
    """Closes 373->exit: renderer without ``_render_annotation`` is a no-op."""
    drawer, _ = _drawer_with_bare_renderer()

    class _Annot:
        def is_hidden(self) -> bool:
            return False

        def is_no_view(self) -> bool:
            return False

        def is_invisible(self) -> bool:
            return False

        def get_appearance_stream(self) -> Any:
            return object()

    # should_skip_annotation may return True for an unconfigured stub;
    # bypass by patching directly.
    drawer.should_skip_annotation = lambda _a: False  # type: ignore[assignment]
    drawer.show_annotation(_Annot())  # type: ignore[arg-type]


def test_show_font_glyph_exits_when_renderer_lacks_render_glyph() -> None:
    """Closes 428->exit: renderer without ``_render_glyph`` is a no-op."""
    drawer, _ = _drawer_with_bare_renderer()
    drawer.show_font_glyph(None, None, 65, None)  # type: ignore[arg-type]


def test_show_transparency_group_on_graphics_with_non_image() -> None:
    """Closes 582->590: when ``graphics`` is NOT a PIL Image, the
    image-rebinding branch is skipped; show_form still runs."""
    drawer, _ = _drawer_with_bare_renderer()

    class _NotAnImage:
        pass

    class _Form:
        pass

    # show_form falls through silently (no _render_form_xobject on the
    # stripped renderer either) — the assertion is just no-raise.
    drawer.show_transparency_group_on_graphics(_Form(), _NotAnImage())  # type: ignore[arg-type]


def test_begin_text_clip_idempotent_when_list_already_present() -> None:
    """Closes 611->exit: when ``_text_clippings`` is already a list,
    no reset happens."""
    drawer, rdr = _drawer_with_bare_renderer()
    existing = ["already-here"]
    rdr._text_clippings = existing
    drawer.begin_text_clip()
    # The pre-existing list is preserved (no reallocation).
    assert rdr._text_clippings is existing


def test_end_text_clip_skips_when_text_clippings_is_none() -> None:
    """Closes 619->exit: a missing/empty ``_text_clippings`` short-circuits."""
    drawer, rdr = _drawer_with_bare_renderer()
    # Ensure no _text_clippings attribute.
    if hasattr(rdr, "_text_clippings"):
        delattr(rdr, "_text_clippings")
    # No exception, no assignment.
    drawer.end_text_clip()
    assert getattr(rdr, "_text_clippings", None) is None


def test_draw_glyph_exits_when_renderer_lacks_draw_glyph_path() -> None:
    """Closes 625->exit: renderer without ``_draw_glyph_path`` is a no-op."""
    drawer, _ = _drawer_with_bare_renderer()
    drawer.draw_glyph(None, None, 0, None, None)


def test_draw_tiling_pattern_exits_when_renderer_lacks_helper() -> None:
    """Closes 633->exit: renderer without ``_paint_tiling_pattern`` is
    a no-op."""
    drawer, _ = _drawer_with_bare_renderer()
    drawer.draw_tiling_pattern(None, None, None)
