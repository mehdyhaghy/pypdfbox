"""Tests for ``ImageType`` enum + ``image_type`` overload on ``PDFRenderer``.

Mirrors upstream ``ImageType.toBufferedImageType()`` and the three-arg
overload of ``PDFRenderer.renderImageWithDPI(int, float, ImageType)``.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.rendering import ImageType, PDFRenderer
from pypdfbox.rendering.image_type import (
    TYPE_3BYTE_BGR,
    TYPE_BYTE_BINARY,
    TYPE_BYTE_GRAY,
    TYPE_INT_ARGB,
    TYPE_INT_RGB,
)


def _make_doc(width: float = 50.0, height: float = 50.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


# ---------------------------------------------------------------------------
# enum surface
# ---------------------------------------------------------------------------


def test_image_type_has_five_values_matching_upstream() -> None:
    names = {member.name for member in ImageType}
    assert names == {"BINARY", "GRAY", "RGB", "ARGB", "BGR"}


@pytest.mark.parametrize(
    ("member", "expected"),
    [
        (ImageType.BINARY, TYPE_BYTE_BINARY),
        (ImageType.GRAY, TYPE_BYTE_GRAY),
        (ImageType.RGB, TYPE_INT_RGB),
        (ImageType.ARGB, TYPE_INT_ARGB),
        (ImageType.BGR, TYPE_3BYTE_BGR),
    ],
)
def test_image_type_to_buffered_image_type_matches_awt(
    member: ImageType, expected: int
) -> None:
    assert member.to_buffered_image_type() == expected


@pytest.mark.parametrize(
    ("member", "expected_mode"),
    [
        (ImageType.BINARY, "1"),
        (ImageType.GRAY, "L"),
        (ImageType.RGB, "RGB"),
        (ImageType.ARGB, "RGBA"),
        (ImageType.BGR, "RGB"),  # Pillow has no packed BGR mode
    ],
)
def test_image_type_pil_mode_returns_pillow_mode_name(
    member: ImageType, expected_mode: str
) -> None:
    assert member.pil_mode == expected_mode


# ---------------------------------------------------------------------------
# render_image / render_image_with_dpi accept ImageType
# ---------------------------------------------------------------------------


def test_render_image_default_keeps_rgb_mode() -> None:
    """Without an explicit image_type the lite renderer keeps RGB."""
    doc, _ = _make_doc()
    img = PDFRenderer(doc).render_image(0)
    assert img.mode == "RGB"


def test_render_image_with_argb_returns_rgba_image() -> None:
    doc, _ = _make_doc()
    img = PDFRenderer(doc).render_image(0, scale=1.0, image_type=ImageType.ARGB)
    assert img.mode == "RGBA"
    # ARGB canvas should start fully transparent so blends compose
    # correctly (matches upstream's ``new Color(0, 0, 0, 0)`` clear).
    alpha = img.getpixel((0, 0))[3]
    assert alpha == 0


def test_render_image_with_gray_returns_l_mode_image() -> None:
    doc, _ = _make_doc()
    img = PDFRenderer(doc).render_image(0, scale=1.0, image_type=ImageType.GRAY)
    assert img.mode == "L"
    # Grayscale background is white (255), not 0 — matches upstream's
    # ``setBackground(Color.WHITE) + clearRect`` for non-ARGB targets.
    assert img.getpixel((0, 0)) == 255


def test_render_image_with_dpi_with_binary_returns_1bit_image() -> None:
    doc, _ = _make_doc()
    img = PDFRenderer(doc).render_image_with_dpi(
        0, dpi=72.0, image_type=ImageType.BINARY
    )
    assert img.mode == "1"


def test_render_image_with_dpi_image_type_does_not_change_dimensions() -> None:
    """ImageType selects pixel format only; width/height come from DPI."""
    doc, _ = _make_doc(width=40.0, height=20.0)
    rgba = PDFRenderer(doc).render_image_with_dpi(
        0, dpi=144.0, image_type=ImageType.ARGB
    )
    assert rgba.size == (80, 40)
