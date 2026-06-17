"""Fuzz the ``PDFRenderer`` image-type / background-fill / mode-mapping path.

Surface: ``PDFRenderer.render_image`` /
``PDFRenderer.render_image_with_dpi`` ``image_type`` argument and the
``ImageType`` enum's ``pil_mode`` / ``to_buffered_image_type`` helpers.

Parity oracle: Apache PDFBox 3.0.x
``PDFRenderer.renderImage(int, float, ImageType, RenderDestination)`` —
upstream allocates a ``BufferedImage`` of ``imageType.toBufferedImageType()``
and, for **every image type except ARGB**, paints an opaque **white**
background (``g.setBackground(Color.WHITE); g.clearRect(...)``). For
``ImageType.ARGB`` it leaves the canvas transparent (``new Color(0,0,0,0)``
clear) so the rendered page composes onto a transparent backdrop.

This pins:
* the PIL mode for each ``ImageType`` (RGB→"RGB", ARGB→"RGBA", GRAY→"L",
  BINARY→"1", BGR→"RGB");
* the ``to_buffered_image_type()`` AWT constant for each;
* a blank-page render in each mode has the right mode + size;
* the **background fill** is opaque white for RGB/GRAY/BINARY/BGR and
  fully **transparent** for ARGB (alpha 0);
* the default ``image_type=None`` keeps the historical opaque white RGB;
* alpha is present **only** for ARGB;
* painted (non-white) content survives the mode/background conversion.
"""

from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.common import PDStream
from pypdfbox.rendering import ImageType, PDFRenderer
from pypdfbox.rendering.image_type import (
    TYPE_3BYTE_BGR,
    TYPE_BYTE_BINARY,
    TYPE_BYTE_GRAY,
    TYPE_INT_ARGB,
    TYPE_INT_RGB,
)

# Image types whose background must be opaque white (everything but ARGB).
_OPAQUE_TYPES = [
    ImageType.RGB,
    ImageType.GRAY,
    ImageType.BINARY,
    ImageType.BGR,
]

# Expected (pil_mode, awt_type) per image type.
_TYPE_EXPECTATIONS = {
    ImageType.BINARY: ("1", TYPE_BYTE_BINARY),
    ImageType.GRAY: ("L", TYPE_BYTE_GRAY),
    ImageType.RGB: ("RGB", TYPE_INT_RGB),
    ImageType.ARGB: ("RGBA", TYPE_INT_ARGB),
    ImageType.BGR: ("RGB", TYPE_3BYTE_BGR),
}


def _make_doc(
    width: float = 30.0, height: float = 20.0, content: bytes | None = None
) -> PDDocument:
    """Single-page document, optionally with a content stream."""
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    if content is not None:
        stream = PDStream(doc)
        with stream.create_output_stream() as out:
            out.write(content)
        page.set_contents(stream)
    return doc


def _opaque_background_value(img: Image.Image) -> object:
    """The expected 'unpainted background' pixel for an opaque mode."""
    if img.mode == "RGB":
        return (255, 255, 255)
    if img.mode in ("L", "1"):
        return 255
    raise AssertionError(f"unexpected opaque mode {img.mode}")


# ---------------------------------------------------------------------------
# ImageType helper surface (direct, no render)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("member", list(ImageType), ids=[m.name for m in ImageType])
def test_pil_mode_matches_upstream_buffered_image_flavour(member: ImageType) -> None:
    expected_mode, _ = _TYPE_EXPECTATIONS[member]
    assert member.pil_mode == expected_mode


@pytest.mark.parametrize("member", list(ImageType), ids=[m.name for m in ImageType])
def test_to_buffered_image_type_matches_awt_constant(member: ImageType) -> None:
    _, expected_awt = _TYPE_EXPECTATIONS[member]
    assert member.to_buffered_image_type() == expected_awt


def test_only_argb_pil_mode_carries_an_alpha_channel() -> None:
    """RGBA is the single alpha-bearing mode; every other maps to a
    mode Pillow treats as opaque."""
    alpha_modes = {m for m in ImageType if "A" in m.pil_mode and m.pil_mode == "RGBA"}
    assert alpha_modes == {ImageType.ARGB}


def test_pil_mode_and_awt_type_are_total_over_the_enum() -> None:
    """No enum member raises on either helper (no KeyError gap)."""
    for member in ImageType:
        assert isinstance(member.pil_mode, str)
        assert isinstance(member.to_buffered_image_type(), int)


# ---------------------------------------------------------------------------
# Blank-page render — mode, size, background fill
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("member", list(ImageType), ids=[m.name for m in ImageType])
def test_blank_render_mode_matches_pil_mode(member: ImageType) -> None:
    doc = _make_doc()
    img = PDFRenderer(doc).render_image(0, 1.0, image_type=member)
    assert img.mode == member.pil_mode


@pytest.mark.parametrize("member", list(ImageType), ids=[m.name for m in ImageType])
def test_image_type_does_not_change_dimensions(member: ImageType) -> None:
    """Image type selects pixel format only; dims come from the page+DPI."""
    doc = _make_doc(width=40.0, height=20.0)
    img = PDFRenderer(doc).render_image_with_dpi(0, dpi=144.0, image_type=member)
    assert img.size == (80, 40)


@pytest.mark.parametrize(
    "member", _OPAQUE_TYPES, ids=[m.name for m in _OPAQUE_TYPES]
)
def test_opaque_types_fill_background_white_not_black(member: ImageType) -> None:
    """Non-ARGB types fill the background opaque white (upstream
    ``setBackground(Color.WHITE)``), never black or transparent."""
    doc = _make_doc()
    img = PDFRenderer(doc).render_image(0, 1.0, image_type=member)
    assert img.getpixel((0, 0)) == _opaque_background_value(img)
    # Sample a few corners — a uniformly white blank page.
    w, h = img.size
    for xy in [(w - 1, 0), (0, h - 1), (w - 1, h - 1), (w // 2, h // 2)]:
        assert img.getpixel(xy) == _opaque_background_value(img)


def test_argb_background_is_fully_transparent() -> None:
    """ARGB leaves the unpainted backdrop transparent (alpha 0),
    mirroring upstream's ``new Color(0, 0, 0, 0)`` clear."""
    doc = _make_doc()
    img = PDFRenderer(doc).render_image(0, 1.0, image_type=ImageType.ARGB)
    assert img.mode == "RGBA"
    w, h = img.size
    for xy in [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]:
        assert img.getpixel(xy)[3] == 0


def test_default_image_type_is_opaque_white_rgb() -> None:
    """``image_type=None`` keeps the historical opaque white RGB canvas,
    matching upstream's RGB default."""
    doc = _make_doc()
    img = PDFRenderer(doc).render_image(0)
    assert img.mode == "RGB"
    assert img.getpixel((0, 0)) == (255, 255, 255)


def test_alpha_channel_present_only_for_argb() -> None:
    """Only the ARGB render exposes an alpha band; the rest are opaque."""
    doc = _make_doc()
    for member in ImageType:
        img = PDFRenderer(doc).render_image(0, 1.0, image_type=member)
        if member is ImageType.ARGB:
            assert img.mode == "RGBA"
            assert "A" in img.getbands()
        else:
            assert "A" not in img.getbands()


# ---------------------------------------------------------------------------
# Painted content survives mode/background conversion
# ---------------------------------------------------------------------------

# Fill the left half of a 30x20 page solid black; right half stays page-white.
_HALF_BLACK = b"0 0 0 rg 0 0 15 20 re f"


@pytest.mark.parametrize("member", list(ImageType), ids=[m.name for m in ImageType])
def test_painted_black_region_distinct_from_background(member: ImageType) -> None:
    """A black fill on the left half stays distinct from the (white /
    transparent) background after the per-type conversion."""
    doc = _make_doc(content=_HALF_BLACK)
    img = PDFRenderer(doc).render_image(0, 1.0, image_type=member)
    w, h = img.size
    left = img.getpixel((w // 4, h // 2))  # painted black
    right = img.getpixel((3 * w // 4, h // 2))  # background
    assert left != right


@pytest.mark.parametrize(
    "member", _OPAQUE_TYPES, ids=[m.name for m in _OPAQUE_TYPES]
)
def test_painted_black_is_zero_in_opaque_modes(member: ImageType) -> None:
    doc = _make_doc(content=_HALF_BLACK)
    img = PDFRenderer(doc).render_image(0, 1.0, image_type=member)
    w, h = img.size
    left = img.getpixel((w // 4, h // 2))
    if img.mode == "RGB":
        assert left == (0, 0, 0)
    else:  # L or "1"
        assert left == 0


def test_argb_painted_black_is_opaque_and_background_transparent() -> None:
    """In ARGB the painted region is opaque black (alpha 255) while the
    untouched background stays transparent (alpha 0)."""
    doc = _make_doc(content=_HALF_BLACK)
    img = PDFRenderer(doc).render_image(0, 1.0, image_type=ImageType.ARGB)
    w, h = img.size
    left = img.getpixel((w // 4, h // 2))
    right = img.getpixel((3 * w // 4, h // 2))
    assert left == (0, 0, 0, 255)
    assert right[3] == 0


# ---------------------------------------------------------------------------
# DPI / scale fuzz across image types — modes + sizes stay coherent
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("dpi", [36.0, 72.0, 96.0, 150.0, 300.0])
def test_modes_stable_across_dpi(dpi: float) -> None:
    doc = _make_doc(width=20.0, height=10.0)
    for member in ImageType:
        img = PDFRenderer(doc).render_image_with_dpi(0, dpi=dpi, image_type=member)
        assert img.mode == member.pil_mode
        assert img.size[0] >= 1 and img.size[1] >= 1


@pytest.mark.parametrize("scale", [0.5, 1.0, 2.0, 3.5])
def test_background_fill_stable_across_scale(scale: float) -> None:
    """The background-fill semantics (white opaque vs transparent) hold
    at every scale, independent of pixel dims."""
    doc = _make_doc()
    for member in _OPAQUE_TYPES:
        img = PDFRenderer(doc).render_image(0, scale, image_type=member)
        assert img.getpixel((0, 0)) == _opaque_background_value(img)
    argb = PDFRenderer(doc).render_image(0, scale, image_type=ImageType.ARGB)
    assert argb.getpixel((0, 0))[3] == 0


# ---------------------------------------------------------------------------
# render_image vs render_image_with_dpi parity for image types
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("member", list(ImageType), ids=[m.name for m in ImageType])
def test_render_image_and_with_dpi_agree_on_mode(member: ImageType) -> None:
    doc = _make_doc()
    a = PDFRenderer(doc).render_image(0, 1.0, image_type=member)
    b = PDFRenderer(doc).render_image_with_dpi(0, dpi=72.0, image_type=member)
    assert a.mode == b.mode == member.pil_mode
    assert a.size == b.size
