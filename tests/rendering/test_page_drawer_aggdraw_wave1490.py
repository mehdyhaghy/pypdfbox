"""Coverage round-out for ``page_drawer`` + ``_aggdraw_compat`` — wave 1490.

Closes the residual defensive fall-backs in :class:`PageDrawer`
(``is_content_rendered`` / ``is_hidden_ocmd`` when the renderer exposes no
helper) and the odd-length-dash duplication arm of the skia stroke-paint
builder in :mod:`pypdfbox.rendering._aggdraw_compat`.
"""

from __future__ import annotations

from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import (
    PageDrawerParameters,
    PDFRenderer,
    RenderDestination,
)
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.page_drawer import PageDrawer

# ---------------------------------------------------------------------------
# PageDrawer defensive fall-backs
# ---------------------------------------------------------------------------


def _make_drawer() -> PageDrawer:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, 40.0, 40.0))
    doc.add_page(page)
    renderer = PDFRenderer(doc)
    params = PageDrawerParameters(
        renderer=renderer,
        page=page,
        subsampling_allowed=False,
        destination=RenderDestination.VIEW,
        rendering_hints={"AA": True},
        image_downscaling_optimization_threshold=0.5,
    )
    return PageDrawer(params)


def test_is_content_rendered_without_helper_returns_true() -> None:
    drawer = _make_drawer()
    # Strip the renderer's _is_content_rendered so the fall-back (line 706)
    # is taken: with no helper the drawer reports content as rendered.
    if hasattr(drawer._renderer, "_is_content_rendered"):
        drawer._renderer._is_content_rendered = None
    assert drawer.is_content_rendered() is True


def test_is_hidden_ocmd_none_is_false() -> None:
    drawer = _make_drawer()
    # Line 726: a None OCMD is never hidden.
    assert drawer.is_hidden_ocmd(None) is False


def test_is_hidden_ocmd_without_helper_returns_false() -> None:
    drawer = _make_drawer()
    # Remove the renderer's property-list resolver so the fall-back
    # (line 730) is taken: with no resolver the OCMD is treated as visible.
    if hasattr(drawer._renderer, "_property_list_is_hidden"):
        drawer._renderer._property_list_is_hidden = None
    assert drawer.is_hidden_ocmd(object()) is False


# ---------------------------------------------------------------------------
# _aggdraw_compat: odd-length dash duplication (line 458)
# ---------------------------------------------------------------------------


def test_odd_length_dash_is_duplicated_and_paints() -> None:
    # An odd-length dash array [3] is duplicated to [3, 3] before being
    # handed to skia's DashPathEffect (line 458). The stroke must still
    # paint a dashed line rather than vanish.
    img = Image.new("RGBA", (40, 4), (255, 255, 255, 255))
    draw = aggdraw.Draw(img)
    draw.setantialias(False)
    path = aggdraw.Path()
    path.moveto(0.0, 2.0)
    path.lineto(40.0, 2.0)
    pen = aggdraw.Pen((0, 0, 0), width=2.0, dash=((3.0,), 0.0))
    draw.path(path, pen=pen)
    draw.flush()
    row = [img.getpixel((x, 2)) for x in range(40)]
    dark = [p for p in row if p[0] < 128]
    light = [p for p in row if p[0] >= 200]
    # A dashed line leaves both painted ("on") and unpainted ("off") runs.
    assert dark, "odd-length dash should still paint on-segments"
    assert light, "odd-length dash should leave off-segments"


def test_even_length_dash_still_paints() -> None:
    img = Image.new("RGBA", (40, 4), (255, 255, 255, 255))
    draw = aggdraw.Draw(img)
    draw.setantialias(False)
    path = aggdraw.Path()
    path.moveto(0.0, 2.0)
    path.lineto(40.0, 2.0)
    pen = aggdraw.Pen((0, 0, 0), width=2.0, dash=((4.0, 4.0), 0.0))
    draw.path(path, pen=pen)
    draw.flush()
    row = [img.getpixel((x, 2)) for x in range(40)]
    assert any(p[0] < 128 for p in row)


def test_degenerate_dash_sum_zero_stays_solid() -> None:
    # A dash whose intervals sum to zero is skipped (the line stays solid),
    # exercising the ``sum(ivals) > 0`` guard rather than vanishing.
    img = Image.new("RGBA", (10, 4), (255, 255, 255, 255))
    draw = aggdraw.Draw(img)
    draw.setantialias(False)
    path = aggdraw.Path()
    path.moveto(0.0, 2.0)
    path.lineto(10.0, 2.0)
    pen = aggdraw.Pen((0, 0, 0), width=2.0, dash=((0.0, 0.0), 0.0))
    draw.path(path, pen=pen)
    draw.flush()
    row = [img.getpixel((x, 2)) for x in range(10)]
    assert any(p[0] < 128 for p in row)
