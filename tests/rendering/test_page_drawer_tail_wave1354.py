"""Wave 1354 tail-sweep for ``PageDrawer``.

Covers:

* ``show_transparency_group`` fallback when the renderer lacks
  ``_render_form_xobject`` (line 410 in ``page_drawer.py``).
* ``is_rectangular`` early-out branches when the first segment is not
  ``M`` (line 742) and when a non-first segment is not ``L`` (line 745).
"""

from __future__ import annotations

from typing import Any

from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import PageDrawerParameters, RenderDestination
from pypdfbox.rendering.page_drawer import PageDrawer
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _GState


def _make_drawer() -> tuple[PDDocument, PDFRenderer, PageDrawer]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    doc.add_page(page)
    renderer = PDFRenderer(doc)
    renderer._image = Image.new("RGB", (100, 100), (255, 255, 255))
    from pypdfbox.rendering import _aggdraw_compat as aggdraw  # noqa: PLC0415

    renderer._draw = aggdraw.Draw(renderer._image)
    renderer._draw.setantialias(True)
    renderer._scale = 1.0
    renderer._gs_stack = [_GState()]
    renderer._subpaths = []
    renderer._current_subpath = None
    renderer._current_point = (0.0, 0.0)
    renderer._pending_clip = None
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.VIEW,
        rendering_hints={"AA": True},
        image_downscaling_optimization_threshold=0.5,
    )
    return doc, renderer, PageDrawer(params)


def test_show_transparency_group_uses_show_form_when_helper_missing() -> None:
    """Without a ``_render_form_xobject`` helper, the fallback path runs
    ``show_form`` (line 410)."""
    doc, renderer, drawer = _make_drawer()
    try:
        # Make absolutely sure no helper exists — pop any attribute the
        # renderer happens to expose so the ``callable`` guard fails.
        for attr in ("_render_form_xobject",):
            if hasattr(renderer, attr):
                try:
                    delattr(renderer, attr)
                except AttributeError:
                    setattr(renderer, attr, None)
        # show_form is a no-op when the renderer also lacks the helper,
        # so just verify the call succeeds and the stack is popped.
        drawer.show_transparency_group(form="form-tx")
        assert drawer._transparency_group_stack == []
    finally:
        doc.close()


def test_is_rectangular_returns_false_when_first_segment_is_not_m() -> None:
    """Five-segment closed path whose first op is ``L`` — line 742."""
    doc, _renderer, drawer = _make_drawer()
    try:
        path: list[Any] = [
            ("L", 0, 0),  # not M
            ("L", 10, 0),
            ("L", 10, 5),
            ("L", 0, 5),
            ("Z",),
        ]
        assert drawer.is_rectangular(path) is False
    finally:
        doc.close()


def test_is_rectangular_returns_false_when_middle_segment_is_not_l() -> None:
    """Five-segment closed path whose second op is ``M`` — line 745.

    The filter at line 737 only keeps ``M``/``L``/``Z`` segments, so we
    insert an extra ``M`` in position 1 (after the leading ``M``) to put
    a non-``L`` in the [1:4] window.
    """
    doc, _renderer, drawer = _make_drawer()
    try:
        path: list[Any] = [
            ("M", 0, 0),
            ("M", 10, 0),  # not L — triggers the early-out at line 745
            ("L", 10, 5),
            ("L", 0, 5),
            ("Z",),
        ]
        assert drawer.is_rectangular(path) is False
    finally:
        doc.close()
