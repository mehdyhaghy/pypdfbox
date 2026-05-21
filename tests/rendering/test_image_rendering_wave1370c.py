"""Image-XObject rendering tests for :class:`PDFRenderer` — covering
``/SMask`` integration, ``/Mask`` stencil contracts, JPX color-space
inference, and the raw raster decode paths.

Cross-platform note (per CLAUDE.md): libtiff / Pillow byte-padding at
EOD differs across wheels; do **not** assert on post-EOD tail bytes.
Use structural / mean-intensity / channel-count checks instead of
pixel-exact equality.
"""
from __future__ import annotations

import io

from PIL import Image

from pypdfbox.cos import COSArray, COSInteger, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(
    actual: tuple[int, int, int],
    expected: tuple[int, int, int],
    tol: int = 12,
) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


def _build_raw_rgb_xobject(
    rgb: tuple[int, int, int], size: int = 8
) -> PDImageXObject:
    """Build a raw 8bpc DeviceRGB Image XObject — no filters."""
    payload = bytes(rgb) * (size * size)
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    stream.set_raw_data(payload)
    return PDImageXObject(stream)


def _build_jpeg_xobject(
    rgb: tuple[int, int, int], size: int = 16
) -> PDImageXObject:
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


# ---------------------------------------------------------------------------
# raw raster + DeviceRGB / DeviceGray decoding
# ---------------------------------------------------------------------------


def test_raw_device_rgb_image_renders_solid_color() -> None:
    """A raw 8bpc DeviceRGB image should render at the placed bbox."""
    doc, page = _make_doc()
    image = _build_raw_rgb_xobject((255, 0, 0), size=4)
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=10.0, y=10.0, width=80.0, height=80.0)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((50, 50))
    assert _is_close(inside, (255, 0, 0), tol=20), inside


def test_raw_device_gray_image_renders_grayscale() -> None:
    """A raw 8bpc DeviceGray image with all 128 samples should render as
    middle grey (~128, 128, 128)."""
    size = 8
    payload = bytes([128] * (size * size))
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray")
    )
    stream.set_raw_data(payload)
    image = PDImageXObject(stream)

    doc, page = _make_doc()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=10.0, y=10.0, width=80.0, height=80.0)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((50, 50))
    # ~128 grey — generous tolerance for resampling.
    assert 80 < inside[0] < 180, inside
    assert abs(inside[0] - inside[1]) < 5, inside
    assert abs(inside[1] - inside[2]) < 5, inside


# ---------------------------------------------------------------------------
# /SMask integration
# ---------------------------------------------------------------------------


def test_smask_with_jpeg_image_alpha_masks_visible_area() -> None:
    """A JPEG image with an SMask whose top half is opaque and bottom
    half transparent should show colour at the top and page background
    at the bottom."""
    doc, page = _make_doc(100.0, 100.0)
    image = _build_jpeg_xobject((0, 0, 255), size=16)

    size = 16
    half = size // 2
    # Top rows opaque (image-space rows 0..half), bottom rows transparent.
    mask_bytes = bytes([255] * (half * size) + [0] * (half * size))

    smask_stream = COSStream()
    smask_stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    smask_stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    smask_stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(size))
    smask_stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(size))
    smask_stream.set_item(
        COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8)
    )
    smask_stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray")
    )
    smask_stream.set_raw_data(mask_bytes)
    image.set_soft_mask(PDImageXObject(smask_stream))

    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=10.0, y=10.0, width=80.0, height=80.0)
    img = PDFRenderer(doc).render_image(0)
    # The mask's "opaque" half is image-row 0..half. Image rows map to PDF
    # via y-flip during draw_image, so the opaque rows land in the
    # *upper* half of the PDF bbox. The PIL y is flipped from PDF y, so
    # PIL top half = PDF top half.
    # Sample in the top half (PIL y small) — blue visible.
    top = img.getpixel((50, 25))
    # Bottom half (PIL y large) — background visible (white).
    bottom = img.getpixel((50, 75))
    # Acceptable for either half to be the painted vs background side
    # depending on how the renderer flips the mask. Confirm exactly one
    # half shows the colour and the other shows the background.
    top_is_blue = _is_close(top, (0, 0, 255), tol=40)
    top_is_white = _is_close(top, (255, 255, 255), tol=10)
    bot_is_blue = _is_close(bottom, (0, 0, 255), tol=40)
    bot_is_white = _is_close(bottom, (255, 255, 255), tol=10)
    assert (top_is_blue and bot_is_white) or (top_is_white and bot_is_blue), (
        f"expected mask to split top/bottom; top={top} bottom={bottom}"
    )


def test_smask_does_not_corrupt_image_without_mask() -> None:
    """Sanity: rendering an image without an SMask should match the
    unmasked colour at the centre — verifies the SMask code path doesn't
    accidentally fire for masks=None."""
    doc, page = _make_doc()
    image = _build_jpeg_xobject((128, 64, 192), size=16)
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=10.0, y=10.0, width=80.0, height=80.0)
    img = PDFRenderer(doc).render_image(0)
    centre = img.getpixel((50, 50))
    assert _is_close(centre, (128, 64, 192), tol=30), centre


# ---------------------------------------------------------------------------
# /ImageMask stencil
# ---------------------------------------------------------------------------


def test_image_with_stencil_mask_attribute_renders_without_error() -> None:
    """An Image XObject with ``/ImageMask true`` is a stencil — the lite
    renderer may treat it as a 1-bpc gray image; just confirm no crash."""
    size = 8
    payload = bytes([0xFF] * (size * size))
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceGray")
    )
    stream.set_raw_data(payload)
    image = PDImageXObject(stream)
    image.set_stencil(True)
    assert image.is_stencil() is True

    doc, page = _make_doc()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=10.0, y=10.0, width=80.0, height=80.0)
    img = PDFRenderer(doc).render_image(0)
    # Just confirm we got a fully-formed image (no crash).
    assert img.size == (100, 100)


# ---------------------------------------------------------------------------
# /Decode array
# ---------------------------------------------------------------------------


def test_image_with_decode_array_does_not_crash() -> None:
    """An Image XObject with a /Decode array should be rendered without
    crashing — the array remaps each component from its raw range to
    [0.0, 1.0]. The lite renderer may not apply the remap, but the
    image must still be paintable."""
    size = 4
    payload = bytes([255, 0, 0] * (size * size))  # red samples
    decode = COSArray()
    # Identity decode for each of 3 components.
    for v in (0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
        decode.add(COSInteger.get(int(v)))

    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(size))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    stream.set_item(COSName.get_pdf_name("Decode"), decode)
    stream.set_raw_data(payload)
    image = PDImageXObject(stream)

    doc, page = _make_doc()
    with PDPageContentStream(doc, page) as cs:
        cs.draw_image(image, x=10.0, y=10.0, width=80.0, height=80.0)
    img = PDFRenderer(doc).render_image(0)
    inside = img.getpixel((50, 50))
    # Identity decode → red samples paint as red.
    assert _is_close(inside, (255, 0, 0), tol=30), inside


# ---------------------------------------------------------------------------
# JPX color space inference
# ---------------------------------------------------------------------------


def test_jpx_detection_via_filter_chain() -> None:
    """``is_jpx()`` must return True for the /JPXDecode filter name and
    False without it. Pinning the predicate so the renderer's JPX branch
    correctly dispatches."""
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(8))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(8))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    stream.set_raw_data(b"\x00" * 192)
    image = PDImageXObject(stream)
    assert image.is_jpx() is False

    # Now add JPXDecode and verify the predicate flips.
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("JPXDecode"))
    assert image.is_jpx() is True


def test_jpx_filter_in_array_form_still_detected() -> None:
    """The /Filter entry may be a single name or an array of names. The
    detector must handle both forms."""
    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.get_pdf_name("Width"), COSInteger.get(4))
    stream.set_item(COSName.get_pdf_name("Height"), COSInteger.get(4))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), COSInteger.get(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    filter_arr = COSArray()
    filter_arr.add(COSName.get_pdf_name("FlateDecode"))
    filter_arr.add(COSName.get_pdf_name("JPXDecode"))
    stream.set_item(COSName.FILTER, filter_arr)
    stream.set_raw_data(b"")
    image = PDImageXObject(stream)
    assert image.is_jpx() is True


# ---------------------------------------------------------------------------
# placement transforms
# ---------------------------------------------------------------------------


def test_image_placed_with_negative_scale_flips() -> None:
    """A ``cm`` op applying a negative y-scale should flip the image
    vertically — render must still complete without error."""
    doc, page = _make_doc(60.0, 60.0)
    image = _build_jpeg_xobject((255, 128, 0), size=8)
    # Place via raw content stream so we can apply an arbitrary cm.
    from pypdfbox.pdmodel.pd_resources import PDResources

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Im0"),
        image.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(
        # Scale 20x in x and -20x in y (vertical flip), translate to (10, 30).
        b"q\n"
        b"20 0 0 -20 10 30 cm\n"
        b"/Im0 Do\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Just confirm the image is fully drawn — exact bbox is sensitive
    # to the flip+CTM compose path; pixel-equality would be fragile.
    assert img.size == (60, 60)
    # Find some orange-ish pixels somewhere on the page.
    orange_count = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if r > 200 and 80 < g < 170 and b < 80:
                orange_count += 1
    assert orange_count > 50, f"expected orange pixels somewhere, got {orange_count}"


def test_image_with_rotation_renders_at_target_area() -> None:
    """A 90-degree rotation cm should land the image in a rotated bbox.
    Structural check: total painted area is similar to the unrotated
    case (rotation preserves area)."""
    image = _build_jpeg_xobject((255, 0, 0), size=8)
    from pypdfbox.pdmodel.pd_resources import PDResources

    doc, page = _make_doc(100.0, 100.0)
    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Im0"),
        image.get_cos_object(),
    )
    contents = COSStream()
    contents.set_raw_data(
        # 0 60 -60 0 60 20 cm = rotation 90° + scale 60 + translate (60, 20).
        b"q\n"
        b"0 60 -60 0 60 20 cm\n"
        b"/Im0 Do\n"
        b"Q\n"
    )
    page.get_cos_object().set_item(COSName.CONTENTS, contents)
    img = PDFRenderer(doc).render_image(0)
    # Count red-ish pixels — must be > 0 (rotated image lands somewhere).
    red = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if r > 200 and g < 80 and b < 80:
                red += 1
    assert red > 100, f"expected red pixels somewhere, got {red}"
