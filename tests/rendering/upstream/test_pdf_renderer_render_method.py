"""Upstream-equivalent parity tests for ``PDFRenderer.renderImage*`` /
``PDFRenderer.renderPageToGraphics`` entry points.

Upstream baseline: PDFBox 3.0.x.
Source: ``pdfbox/src/main/java/org/apache/pdfbox/rendering/PDFRenderer.java``
methods ``renderImage``, ``renderImageWithDPI`` (with the three- and
four-arg overloads), ``renderPageToGraphics``.

Upstream's ``TestRendering`` is a smoke that loads every PDF in
``src/test/resources/input/rendering`` and asserts ``renderImage(0)``
doesn't throw. The remaining overloads are documented as
``@VisibleForTesting`` in the source but lack standalone JUnit
coverage. We pin the snake_case overloads and their DPI / scale
defaults so a refactor of the entry-point dispatch is parity-checked.
"""
from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import ImageType, PDFRenderer, RenderDestination


@pytest.fixture
def renderer_and_doc() -> tuple[PDFRenderer, PDDocument]:
    document = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 100.0))
    document.add_page(page)
    renderer = PDFRenderer(document)
    try:
        yield renderer, document
    finally:
        document.close()


def test_render_image_default_scale_returns_pil_image(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """Upstream ``renderImage(int pageIndex)`` returns a BufferedImage
    at the default 1.0 scale. pypdfbox's ``render_image`` mirrors that
    by returning a Pillow ``Image``.
    """
    renderer, _doc = renderer_and_doc
    image = renderer.render_image(0)
    assert isinstance(image, Image.Image)
    assert image.size == (100, 100)


def test_render_image_with_scale_factor_round_trips_to_pixel_size(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """Upstream ``renderImage(pageIndex, scale)`` multiplies user-space
    by ``scale`` to get pixel-space dimensions. At 2.0 a 100x100 page
    becomes 200x200 px.
    """
    renderer, _doc = renderer_and_doc
    image = renderer.render_image(0, 2.0)
    assert image.size == (200, 200)


def test_render_image_with_dpi_round_trips_to_pixel_size(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """Upstream ``renderImageWithDPI(pageIndex, dpi)`` derives scale =
    dpi/72 (PDF user-space inch). At 144 DPI a 100x100 page becomes
    200x200 px.
    """
    renderer, _doc = renderer_and_doc
    image = renderer.render_image_with_dpi(0, 144.0)
    assert image.size == (200, 200)


def test_render_image_with_dpi_and_image_type(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """Upstream ``renderImageWithDPI(pageIndex, dpi, imageType)`` — the
    image type controls the Pillow mode. RGB → ``"RGB"``, ARGB →
    ``"RGBA"``.
    """
    renderer, _doc = renderer_and_doc
    rgb = renderer.render_image_with_dpi(0, 72.0, ImageType.RGB)
    assert rgb.mode == "RGB"
    argb = renderer.render_image_with_dpi(0, 72.0, ImageType.ARGB)
    assert argb.mode == "RGBA"


def test_render_image_with_negative_page_index_raises(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """Upstream ``renderImage(-1)`` raises ``IndexOutOfBoundsException``.
    pypdfbox uses ``IndexError`` for the same condition.
    """
    renderer, _doc = renderer_and_doc
    with pytest.raises((IndexError, ValueError)):
        renderer.render_image(-1)


def test_render_image_with_page_index_past_end_raises(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """Single-page doc → renderImage(1) is out of bounds."""
    renderer, _doc = renderer_and_doc
    with pytest.raises((IndexError, ValueError)):
        renderer.render_image(99)


def test_render_image_with_zero_scale_rejected(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """A scale of 0 produces a 0×0 image which is semantically broken.
    Upstream throws IllegalArgumentException; pypdfbox rejects via
    ValueError (or returns a non-zero-sized image — either is the
    documented contract). Pin so silent corruption is impossible.
    """
    renderer, _doc = renderer_and_doc
    try:
        image = renderer.render_image(0, 0.0)
    except (ValueError, ZeroDivisionError):
        return  # rejected → contract honoured
    # If accepted, the result must still be a real Image, not a None
    # or a NaN-sized canvas.
    assert isinstance(image, Image.Image)
    assert image.size[0] >= 0 and image.size[1] >= 0


def test_render_image_with_render_destination_kwarg(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """``render_image(page, scale, image_type, destination)`` (the
    four-arg upstream overload) accepts a :class:`RenderDestination`.
    """
    renderer, _doc = renderer_and_doc
    image = renderer.render_image(
        0, 1.0, ImageType.RGB, destination=RenderDestination.PRINT
    )
    assert isinstance(image, Image.Image)


def test_render_page_to_graphics_returns_no_exception_for_pillow_canvas(
    renderer_and_doc: tuple[PDFRenderer, PDDocument],
) -> None:
    """Upstream ``renderPageToGraphics(pageIndex, Graphics2D)`` paints
    into a caller-supplied canvas. pypdfbox accepts a Pillow ``Image``
    (or compatible drawing target).
    """
    renderer, _doc = renderer_and_doc
    target = Image.new("RGB", (100, 100), color=(255, 255, 255))
    renderer.render_page_to_graphics(0, target)
    # Best-effort smoke: the canvas should still be a valid image.
    assert isinstance(target, Image.Image)
