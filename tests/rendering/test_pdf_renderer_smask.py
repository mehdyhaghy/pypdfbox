"""Tests for SMask alpha compositing + transparency-group rendering in
:class:`pypdfbox.rendering.PDFRenderer`. See PDF spec §11.4.7 / §11.6.5.
"""

from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(actual: tuple[int, int, int], expected: tuple[int, int, int], tol: int = 8) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


def _build_solid_jpeg_xobject(rgb: tuple[int, int, int], size: int = 16) -> PDImageXObject:
    src = Image.new("RGB", (size, size), rgb)
    buf = io.BytesIO()
    src.save(buf, format="JPEG", quality=95)
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("DCTDecode"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    stream.set_raw_data(buf.getvalue())
    return PDImageXObject(stream)


def _build_smask(size: int, mask_bytes: bytes) -> PDImageXObject:
    """Build a raw 8-bit DeviceGray Image XObject from ``mask_bytes``.

    The bytes must already be ``size * size`` long. Mode 'L' values are
    used directly as alpha by :meth:`PDFRenderer._apply_smask`."""
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray")
    )
    stream.set_raw_data(mask_bytes)
    return PDImageXObject(stream)


# ---------------------------------------------------------------------------
# SMask alpha
# ---------------------------------------------------------------------------


def test_smask_makes_transparent_region_show_canvas() -> None:
    """Image with an SMask whose left half is opaque (255) and right
    half is transparent (0). The painted result should show the image's
    colour on the left and the white page background on the right."""
    doc, page = _make_doc(100.0, 100.0)
    image = _build_solid_jpeg_xobject((255, 0, 0), size=16)

    # Build a 16x16 alpha mask: left columns opaque (255), right columns transparent (0).
    size = 16
    half = size // 2
    mask_bytes = bytearray()
    for _ in range(size):
        mask_bytes.extend([255] * half)
        mask_bytes.extend([0] * (size - half))
    smask = _build_smask(size, bytes(mask_bytes))
    image.set_soft_mask(smask)

    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=20.0, y=20.0, width=60.0, height=60.0)

    img = PDFRenderer(doc).render_image(0)

    # Pasted bbox spans PDF (20..80, 20..80) → PIL y flipped, full
    # bbox at PIL (20..80, 20..80). Mask left-opaque → PIL left half
    # (x≈30) shows red; mask right-transparent → PIL right half (x≈70)
    # shows white. Pillow vertical flip in _paste_image preserves the
    # left/right orientation of the alpha.
    left_inside = img.getpixel((30, 50))
    right_inside = img.getpixel((70, 50))
    assert _is_close(left_inside, (255, 0, 0), tol=20), left_inside
    assert _is_close(right_inside, (255, 255, 255), tol=8), right_inside


def test_smask_fully_opaque_matches_unmasked_render() -> None:
    """An all-255 SMask is a no-op visually. Verifies the SMask path
    doesn't corrupt fully-opaque images."""
    doc, page = _make_doc(100.0, 100.0)
    image = _build_solid_jpeg_xobject((0, 128, 255), size=8)
    smask = _build_smask(8, bytes([255] * (8 * 8)))
    image.set_soft_mask(smask)

    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=10.0, y=10.0, width=80.0, height=80.0)

    img = PDFRenderer(doc).render_image(0)
    centre = img.getpixel((50, 50))
    assert _is_close(centre, (0, 128, 255), tol=20), centre


def test_smask_fully_transparent_keeps_canvas_white() -> None:
    """All-zero alpha → the image should not appear at all."""
    doc, page = _make_doc(100.0, 100.0)
    image = _build_solid_jpeg_xobject((0, 200, 0), size=8)
    smask = _build_smask(8, bytes([0] * (8 * 8)))
    image.set_soft_mask(smask)

    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=10.0, y=10.0, width=80.0, height=80.0)

    img = PDFRenderer(doc).render_image(0)
    centre = img.getpixel((50, 50))
    assert _is_close(centre, (255, 255, 255), tol=4), centre


# ---------------------------------------------------------------------------
# transparency group
# ---------------------------------------------------------------------------


def test_transparency_group_renders_inner_content() -> None:
    """A Form XObject marked /Group/S=/Transparency should still render
    its inner painting onto the page (parity smoke test for the
    alpha-composite path)."""
    doc, page = _make_doc(100.0, 100.0)

    # Form draws a green 20x20 square at (10, 10).
    form_stream = COSStream()
    form_stream.set_raw_data(
        b"0 1 0 rg\n"
        b"10 10 20 20 re\n"
        b"f\n"
    )
    form = PDFormXObject(form_stream)
    form.set_b_box(PDRectangle(0.0, 0.0, 100.0, 100.0))

    # Mark as a transparency group via /Group/S=/Transparency.
    from pypdfbox.cos import COSDictionary

    group_dict = COSDictionary()
    group_dict.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    form.set_group(group_dict)

    page_dict = page.get_cos_object()
    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"1 0 0 1 40 40 cm\n"
        b"/Form0 Do\n"
        b"Q\n"
    )
    page_dict.set_item(COSName.CONTENTS, contents)

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Form0"),
        form.get_cos_object(),
    )

    img = PDFRenderer(doc).render_image(0)
    # Form's (10..30, 10..30) shifted by (40, 40) → PDF (50..70, 50..70).
    # PIL y flipped so (50, 30..50). Sample a point inside.
    inside = img.getpixel((60, 40))
    outside = img.getpixel((10, 90))
    assert _is_close(inside, (0, 255, 0), tol=12), inside
    assert _is_close(outside, (255, 255, 255), tol=4), outside


def test_is_transparency_group_helper_via_group_dict() -> None:
    """The internal classifier should recognise /Group/S=/Transparency."""
    from pypdfbox.cos import COSDictionary

    form_stream = COSStream()
    form = PDFormXObject(form_stream)
    assert PDFRenderer._is_transparency_group(form) is False

    group = COSDictionary()
    group.set_item(COSName.get_pdf_name("S"), COSName.get_pdf_name("Transparency"))
    form.set_group(group)
    assert PDFRenderer._is_transparency_group(form) is True


def test_apply_smask_returns_rgba_with_mask_alpha() -> None:
    """Direct exercise of the helper: a 4x4 image + a 4x4 vertical-stripe
    mask should produce an RGBA image whose alpha channel matches the mask."""
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    image = Image.new("RGB", (4, 4), (10, 20, 30))
    smask = _build_smask(4, bytes([0, 64, 128, 255] * 4))

    out = renderer._apply_smask(image, smask)
    assert out.mode == "RGBA"
    assert out.size == (4, 4)
    # Alpha should match the mask byte pattern at row 0.
    alpha = out.split()[3]
    assert list(alpha.crop((0, 0, 4, 1)).tobytes()) == [0, 64, 128, 255]
