"""Wave 1385 — image XObject (``Do``) handler hardening.

Before wave 1385 the renderer's ``_op_do`` and ``_decode_image_xobject``
silently dropped three classes of image XObject:

1. **Stencil masks** (``/ImageMask true``) — upstream PageDrawer
   paints these as alpha mattes in the current non-stroking colour.
   We dropped them because there was no stencil branch and the
   colour-space resolver short-circuited to ``None`` for stencils.

2. **Non-``Device*`` colour spaces** — the old dispatch used
   ``image.get_color_space().name``, which raises ``AttributeError``
   on ``PDICCBased`` / ``PDIndexed`` / ``PDSeparation`` / ``PDDeviceN``
   / ``PDCalRGB`` / ``PDCalGray`` / ``PDLab`` (none of those wrappers
   expose a literal ``.name`` attribute). The exception fell into the
   outer ``_op_do`` ``except`` and the image was dropped.

3. **Form-XObject recursion** — no cap. Upstream
   ``DrawObject.java:84-89`` caps at 50 levels to defend against
   malformed PDFs that nest ``Do`` self-references and blow the
   rasteriser's call stack.

These tests pin the post-wave-1385 contract.
"""

from __future__ import annotations

import pytest
from PIL import Image

from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.graphics.color.pd_device_rgb import PDDeviceRGB
from pypdfbox.pdmodel.graphics.color.pd_icc_based import PDICCBased
from pypdfbox.pdmodel.graphics.color.pd_indexed import PDIndexed
from pypdfbox.pdmodel.graphics.color.pd_separation import PDSeparation
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.image import PDImageXObject
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------- helpers


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(actual, expected, tol=20):
    return all(abs(a - e) <= tol for a, e in zip(actual[:3], expected, strict=True))


# ---------------------------------------------------------------- (1) stencil mask


def test_stencil_mask_paints_in_current_non_stroking_color() -> None:
    """An image XObject with ``/ImageMask true`` paints as the active
    non-stroking colour wherever the matte sample is 0 (opaque under the
    default ``/Decode [0 1]``). Pre-wave-1385 the stencil was dropped.
    """
    doc, page = _make_doc(60.0, 60.0)
    try:
        # 4x4 stencil — top row opaque (0 bits), bottom three rows
        # transparent (1 bits). 1 bpc packed → 1 byte per row.
        # Row 0: 0b00000000 = 0x00 (4 opaque samples, top 4 bits used)
        # Rows 1-3: 0b11110000 = 0xF0 (4 transparent samples)
        stencil_bytes = bytes([0x00, 0xF0, 0xF0, 0xF0])

        stream = COSStream()
        stream.set_raw_data(stencil_bytes)
        image = PDImageXObject(stream)
        image.set_width(4)
        image.set_height(4)
        image.set_bits_per_component(1)
        image.set_stencil(True)

        # Place the stencil at (10, 10) sized 40x40 and paint in red.
        contents = COSStream()
        contents.set_raw_data(
            b"1 0 0 rg\nq\n40 0 0 40 10 10 cm\n/Im0 Do\nQ\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)

        res = PDResources()
        page.set_resources(res)
        res.put(
            COSName.get_pdf_name("XObject"),
            COSName.get_pdf_name("Im0"),
            image.get_cos_object(),
        )

        img = PDFRenderer(doc).render_image(0)
        # The stencil's row-0 opaque samples produce red pixels after
        # the PDF→PIL y-flip near the bottom of the rendered bbox (the
        # canvas is 60x60, bbox spans device y=10..50, opaque row lands
        # at PIL y ≈ 45). Three transparent rows leave the rest of the
        # bbox as the page background (white).
        red_count = 0
        white_count = 0
        for x in range(15, 45, 3):
            for y in range(10, 50, 3):
                px = img.getpixel((x, y))
                if _is_close(px, (255, 0, 0), tol=80):
                    red_count += 1
                elif _is_close(px, (255, 255, 255), tol=10):
                    white_count += 1
        assert red_count > 0, "no red pixels — stencil dropped"
        assert white_count > 0, "no background — stencil opaque everywhere"
    finally:
        doc.close()


# ---------------------------------------------------------------- (2) ICCBased


def test_icc_based_image_decodes_via_color_space_transform() -> None:
    """A ``/ColorSpace /ICCBased`` 3-channel image must decode through
    the wrapper's ``to_rgb_image`` (falls back through ``/Alternate
    /DeviceRGB``) rather than raising AttributeError. Pre-wave-1385 it
    was dropped silently.
    """
    doc, page = _make_doc(40.0, 40.0)
    try:
        # 2x2 ICCBased RGB raster: red, green, blue, white.
        raster = bytes(
            [
                255, 0, 0,
                0, 255, 0,
                0, 0, 255,
                255, 255, 255,
            ]
        )
        stream = COSStream()
        stream.set_raw_data(raster)
        image = PDImageXObject(stream)
        image.set_width(2)
        image.set_height(2)
        image.set_bits_per_component(8)

        # Build a minimal /Alternate /DeviceRGB ICCBased; the body of
        # the ICC stream is irrelevant for the alt-CS code path.
        icc_stream = COSStream()
        icc_stream.set_int("N", 3)
        icc_stream.set_item(
            "Alternate", PDDeviceRGB.INSTANCE.get_cos_object()
        )
        icc_array = COSArray()
        icc_array.add(COSName.get_pdf_name("ICCBased"))
        icc_array.add(icc_stream)
        # Confirm we built it correctly via the typed wrapper before
        # handing the raw array to the image.
        cs = PDICCBased(icc_array)
        assert cs.get_name() == "ICCBased"
        image.set_color_space(cs)

        contents = COSStream()
        contents.set_raw_data(
            b"q\n40 0 0 40 0 0 cm\n/Im0 Do\nQ\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)

        res = PDResources()
        page.set_resources(res)
        res.put(
            COSName.get_pdf_name("XObject"),
            COSName.get_pdf_name("Im0"),
            image.get_cos_object(),
        )

        img = PDFRenderer(doc).render_image(0)
        # Render is 40x40, and the 2x2 image upscales to fill. The
        # important assertion is "render didn't drop the image": at
        # least one non-white pixel must exist somewhere.
        has_colour = False
        for x in (5, 15, 25, 35):
            for y in (5, 15, 25, 35):
                px = img.getpixel((x, y))
                if not _is_close(px, (255, 255, 255), tol=10):
                    has_colour = True
                    break
            if has_colour:
                break
        assert has_colour, "ICCBased image dropped"
    finally:
        doc.close()


# ---------------------------------------------------------------- (3) Indexed


def test_indexed_image_decodes_through_palette_lookup() -> None:
    """A ``/ColorSpace [/Indexed /DeviceRGB N <lookup-bytes>]`` image
    must decode indexed samples through the palette LUT. Pre-wave-1385
    it was dropped (no ``.name`` on PDIndexed).
    """
    doc, page = _make_doc(40.0, 40.0)
    try:
        # 4-entry palette: red, green, blue, white.
        palette = bytes(
            [
                255, 0, 0,
                0, 255, 0,
                0, 0, 255,
                255, 255, 255,
            ]
        )
        # 2x2 sample raster: indices 0, 1, 2, 3
        sample = bytes([0, 1, 2, 3])

        stream = COSStream()
        stream.set_raw_data(sample)
        image = PDImageXObject(stream)
        image.set_width(2)
        image.set_height(2)
        image.set_bits_per_component(8)

        # Build /ColorSpace [/Indexed /DeviceRGB 3 <palette>]
        cs_array = COSArray()
        cs_array.add(COSName.get_pdf_name("Indexed"))
        cs_array.add(PDDeviceRGB.INSTANCE.get_cos_object())
        cs_array.add(COSInteger.get(3))
        cs_array.add(COSString(palette))
        cs = PDIndexed(cs_array)
        assert cs.get_name() == "Indexed"
        image.set_color_space(cs)

        contents = COSStream()
        contents.set_raw_data(
            b"q\n40 0 0 40 0 0 cm\n/Im0 Do\nQ\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)

        res = PDResources()
        page.set_resources(res)
        res.put(
            COSName.get_pdf_name("XObject"),
            COSName.get_pdf_name("Im0"),
            image.get_cos_object(),
        )

        img = PDFRenderer(doc).render_image(0)
        # Image upscales — must have at least one non-white pixel.
        has_colour = False
        for x in (5, 15, 25, 35):
            for y in (5, 15, 25, 35):
                px = img.getpixel((x, y))
                if not _is_close(px, (255, 255, 255), tol=10):
                    has_colour = True
                    break
            if has_colour:
                break
        assert has_colour, "Indexed image dropped"
    finally:
        doc.close()


# ---------------------------------------------------------------- (4) Separation


def test_separation_image_decodes_through_tint_transform() -> None:
    """A ``/ColorSpace /Separation`` 1-channel image must decode
    through the wrapper's tint transform (PostScript Type 4 function
    that emits CMYK) and forward to the alternate's transform. The
    typed wrapper handles this via ``to_pil_image`` — we just verify
    the post-wave-1385 dispatch keeps the upstream behaviour intact.
    """
    doc, page = _make_doc(40.0, 40.0)
    try:
        # Single-pixel separation image at full tint (255 = 1.0).
        stream = COSStream()
        stream.set_raw_data(bytes([255]))
        image = PDImageXObject(stream)
        image.set_width(1)
        image.set_height(1)
        image.set_bits_per_component(8)

        # PostScript Type 4 tint that emits magenta in CMYK
        # (1.0 → [0 1 0 0]).
        tint = COSStream()
        tint.set_int("FunctionType", 4)
        domain = COSArray()
        domain.add(COSFloat(0.0))
        domain.add(COSFloat(1.0))
        tint.set_item("Domain", domain)
        rng = COSArray()
        for v in (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0):
            rng.add(COSFloat(v))
        tint.set_item("Range", rng)
        tint.set_raw_data(b"{ 0 exch 0 0 }")

        cs_array = COSArray()
        cs_array.add(COSName.get_pdf_name("Separation"))
        cs_array.add(COSName.get_pdf_name("SpotMagenta"))
        cs_array.add(COSName.get_pdf_name("DeviceCMYK"))
        cs_array.add(tint)
        cs = PDSeparation(cs_array)
        assert cs.get_name() == "Separation"
        image.set_color_space(cs)

        contents = COSStream()
        contents.set_raw_data(
            b"q\n40 0 0 40 0 0 cm\n/Im0 Do\nQ\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)

        res = PDResources()
        page.set_resources(res)
        res.put(
            COSName.get_pdf_name("XObject"),
            COSName.get_pdf_name("Im0"),
            image.get_cos_object(),
        )

        img = PDFRenderer(doc).render_image(0)
        # Magenta = (255, 0, 255) in sRGB. Centre pixel of the 40x40
        # bbox should land somewhere near magenta.
        center = img.getpixel((20, 20))
        assert _is_close(center, (255, 0, 255), tol=40), f"center={center}"
    finally:
        doc.close()


# ---------------------------------------------------------------- (5) recursion cap


def test_form_xobject_recursion_cap_prevents_stack_overflow() -> None:
    """A Form XObject whose content stream ``Do``s itself recursively
    must trip the wave-1385 recursion cap and return cleanly instead
    of blowing the Python call stack. Mirrors upstream
    ``DrawObject.java:84-89``.
    """
    doc, page = _make_doc(40.0, 40.0)
    try:
        # Build a 51-deep linear chain: Fm0 -> Fm1 -> ... -> Fm50
        # The 51st nested Do should be rejected by the cap (limit=50,
        # so once depth reaches 50 the next Do returns immediately).
        page_res = PDResources()
        page.set_resources(page_res)
        last_form = None
        for i in range(51, -1, -1):
            stream = COSStream()
            if last_form is None:
                # Innermost form — paint a red square.
                stream.set_raw_data(b"1 0 0 rg\n0 0 40 40 re\nf\n")
            else:
                # Refer to the next-deeper form.
                stream.set_raw_data(f"/Fm{i + 1} Do\n".encode("ascii"))
            form = PDFormXObject(stream)
            form.set_b_box(PDRectangle(0.0, 0.0, 40.0, 40.0))
            # Each form needs its own /Resources entry referencing the
            # next form down the chain, so the form's local resource
            # dispatch finds it.
            form_res = PDResources()
            if last_form is not None:
                form_res.put(
                    COSName.get_pdf_name("XObject"),
                    COSName.get_pdf_name(f"Fm{i + 1}"),
                    last_form.get_cos_object(),
                )
            form.set_resources(form_res)
            last_form = form

        # Outer page references Fm0.
        page_res.put(
            COSName.get_pdf_name("XObject"),
            COSName.get_pdf_name("Fm0"),
            last_form.get_cos_object(),
        )
        contents = COSStream()
        contents.set_raw_data(b"q\n/Fm0 Do\nQ\n")
        page.get_cos_object().set_item(COSName.CONTENTS, contents)

        # The critical assertion: the render must complete without a
        # RecursionError. We do not assert on visible pixels — at
        # depth=50 the cap fires before the leaf paint reaches the
        # page, so the canvas may stay white. The behaviour we care
        # about is "does not crash".
        img = PDFRenderer(doc).render_image(0)
        assert isinstance(img, Image.Image)
    finally:
        doc.close()


def test_form_xobject_recursion_cap_is_per_invocation() -> None:
    """The recursion cap is keyed on depth, not invocation count.
    Calling the same form once at depth 0 must succeed (i.e. the
    counter resets between ``Do``s at the same nesting level).
    """
    doc, page = _make_doc(40.0, 40.0)
    try:
        # One form, two consecutive Do calls.
        form_stream = COSStream()
        form_stream.set_raw_data(b"1 0 0 rg\n0 0 20 20 re\nf\n")
        form = PDFormXObject(form_stream)
        form.set_b_box(PDRectangle(0.0, 0.0, 20.0, 20.0))

        res = PDResources()
        page.set_resources(res)
        res.put(
            COSName.get_pdf_name("XObject"),
            COSName.get_pdf_name("Fm0"),
            form.get_cos_object(),
        )
        contents = COSStream()
        contents.set_raw_data(
            b"q\n1 0 0 1 0 0 cm\n/Fm0 Do\nQ\n"
            b"q\n1 0 0 1 20 20 cm\n/Fm0 Do\nQ\n"
        )
        page.get_cos_object().set_item(COSName.CONTENTS, contents)

        img = PDFRenderer(doc).render_image(0)
        # First placement at (0,0): some pixel in y close to top should
        # be red (PDF y=0..20 → PIL y=20..40 in a 40-tall canvas).
        # Second placement at (20,20) → PIL y=0..20.
        # Sample both regions for red.
        first = any(
            _is_close(img.getpixel((5, y)), (255, 0, 0), tol=30)
            for y in (25, 30, 35)
        )
        second = any(
            _is_close(img.getpixel((25, y)), (255, 0, 0), tol=30)
            for y in (5, 10, 15)
        )
        assert first or second, "neither Do placement painted"
    finally:
        doc.close()


# ---------------------------------------------------------------- bonus: get_name parity


@pytest.mark.parametrize(
    "wrapper",
    [
        PDDeviceRGB.INSTANCE,
        PDIndexed(),
        PDICCBased(),
    ],
    ids=["device_rgb", "indexed_default", "icc_based_default"],
)
def test_color_space_wrappers_expose_get_name(wrapper) -> None:
    """Every PDColorSpace subclass must answer ``get_name()`` so the
    wave-1385 dispatch in ``_decode_image_xobject`` can identify it."""
    assert isinstance(wrapper.get_name(), str)
    assert wrapper.get_name()
