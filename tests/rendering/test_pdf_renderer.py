from __future__ import annotations

import io

import pytest
from PIL import Image

from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_doc(width: float = 100.0, height: float = 100.0) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    # Replace the default Letter page with a smaller one so test renders
    # are tractable in pixel space.
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _is_close(actual: tuple[int, int, int], expected: tuple[int, int, int], tol: int = 8) -> bool:
    return all(abs(a - e) <= tol for a, e in zip(actual, expected, strict=True))


# ---------------------------------------------------------------------------
# basic surface
# ---------------------------------------------------------------------------


def test_empty_page_renders_white_image_of_right_size() -> None:
    doc, _ = _make_doc(120.0, 80.0)
    renderer = PDFRenderer(doc)
    img = renderer.render_image(0)  # default scale=1.0 → 1px per pt
    assert img.size == (120, 80)
    # All pixels should be white.
    assert img.getpixel((0, 0)) == (255, 255, 255)
    assert img.getpixel((60, 40)) == (255, 255, 255)
    assert img.getpixel((119, 79)) == (255, 255, 255)


def test_render_image_with_dpi_doubles_dimensions_at_144() -> None:
    doc, _ = _make_doc(50.0, 50.0)
    renderer = PDFRenderer(doc)
    img72 = renderer.render_image_with_dpi(0, dpi=72.0)
    img144 = renderer.render_image_with_dpi(0, dpi=144.0)
    assert img72.size == (50, 50)
    assert img144.size == (100, 100)


def test_filled_red_rectangle_lands_inside_bbox() -> None:
    doc, page = _make_doc(100.0, 100.0)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(1.0, 0.0, 0.0)
        cs.add_rect(20.0, 20.0, 60.0, 60.0)
        cs.fill()
    renderer = PDFRenderer(doc)
    img = renderer.render_image(0)
    # PDF y-axis points up; PIL y-axis points down.
    # Rect (20,20)-(80,80) in PDF maps to y∈[20,80] in PIL after flip.
    inside = img.getpixel((50, 50))
    outside = img.getpixel((5, 5))
    assert _is_close(inside, (255, 0, 0)), inside
    assert _is_close(outside, (255, 255, 255)), outside


# ---------------------------------------------------------------------------
# anti-aliasing
# ---------------------------------------------------------------------------


def test_diagonal_stroke_produces_antialiased_edge() -> None:
    """Without aggdraw a diagonal would be pure 0/255 step pixels; with
    aggdraw at least one mid-grey pixel must show on the edge."""
    doc, page = _make_doc(100.0, 100.0)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.set_line_width(1.0)
        cs.move_to(10.0, 10.0)
        cs.line_to(90.0, 90.0)
        cs.stroke()
    renderer = PDFRenderer(doc)
    img = renderer.render_image(0)
    # Sample every pixel — at least one should be mid-grey (not 0 or 255).
    width, height = img.size
    mid_grey_count = 0
    for y in range(height):
        for x in range(width):
            r, g, b = img.getpixel((x, y))
            if r == g == b and 0 < r < 255:
                mid_grey_count += 1
    assert mid_grey_count > 0, "expected antialiased edge pixels but none found"


# ---------------------------------------------------------------------------
# graphics state stack
# ---------------------------------------------------------------------------


def test_q_Q_stack_isolates_fill_color() -> None:
    doc, page = _make_doc(100.0, 100.0)
    with PDPageContentStream(doc, page) as cs:
        # Outer: green rect at (10,10)-(40,40)
        cs.set_non_stroking_color_rgb(0.0, 1.0, 0.0)
        cs.add_rect(10.0, 10.0, 30.0, 30.0)
        cs.fill()
        # Push, change to blue, draw rect at (50,50)-(80,80), pop
        cs.save_graphics_state()
        cs.set_non_stroking_color_rgb(0.0, 0.0, 1.0)
        cs.add_rect(50.0, 50.0, 30.0, 30.0)
        cs.fill()
        cs.restore_graphics_state()
        # After pop, fill colour should revert to green; new rect at (10,60)
        cs.add_rect(10.0, 60.0, 20.0, 20.0)
        cs.fill()
    img = PDFRenderer(doc).render_image(0)
    # Green rect centred around (25, 75) in PIL (y = 100 - 25)
    assert _is_close(img.getpixel((25, 75)), (0, 255, 0))
    # Blue rect around (65, 35) in PIL
    assert _is_close(img.getpixel((65, 35)), (0, 0, 255))
    # Restored-green rect around (20, 30) in PIL
    assert _is_close(img.getpixel((20, 30)), (0, 255, 0))


# ---------------------------------------------------------------------------
# CTM / cm
# ---------------------------------------------------------------------------


def test_cm_translation_shifts_shape_to_new_pixel_position() -> None:
    doc, page = _make_doc(100.0, 100.0)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(1.0, 0.0, 0.0)
        # First rect — no transform — at (10,10)-(30,30)
        cs.add_rect(10.0, 10.0, 20.0, 20.0)
        cs.fill()
        # Push, translate by (40, 40), draw same rect (which lands at 50..70)
        cs.save_graphics_state()
        cs.transform(1, 0, 0, 1, 40, 40)
        cs.add_rect(10.0, 10.0, 20.0, 20.0)
        cs.fill()
        cs.restore_graphics_state()
    img = PDFRenderer(doc).render_image(0)
    # Original rect (10..30 in PDF, y flipped → 70..90 in PIL)
    assert _is_close(img.getpixel((20, 80)), (255, 0, 0))
    # Translated rect (50..70 in PDF, y flipped → 30..50 in PIL)
    assert _is_close(img.getpixel((60, 40)), (255, 0, 0))


# ---------------------------------------------------------------------------
# even-odd fill rule
# ---------------------------------------------------------------------------


def test_even_odd_fill_creates_hole_in_self_intersecting_path() -> None:
    """Two nested rectangles painted with f* should produce an annulus
    (hole inside)."""
    doc, page = _make_doc(100.0, 100.0)
    # PDPageContentStream doesn't expose f*/B* directly, so we craft the
    # raw operator stream and assign it as the page contents.
    page_dict = page.get_cos_object()
    from pypdfbox.cos import COSName, COSStream

    contents = COSStream()
    body = (
        b"1 0 0 rg\n"  # red fill
        b"10 10 80 80 re\n"  # outer rect
        b"30 30 40 40 re\n"  # inner rect
        b"f*\n"
    )
    contents.set_raw_data(body)
    page_dict.set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # Outer ring filled red
    assert _is_close(img.getpixel((15, 50)), (255, 0, 0))
    # Inner hole white (background)
    assert _is_close(img.getpixel((50, 50)), (255, 255, 255))
    # Outside the outer rect — also white
    assert _is_close(img.getpixel((5, 5)), (255, 255, 255))


# ---------------------------------------------------------------------------
# image XObject
# ---------------------------------------------------------------------------


def test_jpeg_image_xobject_appears_in_render() -> None:
    doc, page = _make_doc(100.0, 100.0)
    # Build a tiny JPEG payload (10x10 solid red).
    src = Image.new("RGB", (10, 10), (255, 0, 0))
    buf = io.BytesIO()
    src.save(buf, format="JPEG", quality=95)
    jpeg_bytes = buf.getvalue()

    # Construct a minimal PDImageXObject around a COSStream carrying the
    # JPEG bytes with /Filter /DCTDecode.
    from pypdfbox.cos import COSName, COSStream
    from pypdfbox.pdmodel.graphics.image.pd_image_x_object import (
        PDImageXObject,
    )

    stream = COSStream()
    stream.set_item(COSName.TYPE, COSName.get_pdf_name("XObject"))
    stream.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Image"))
    stream.set_item(COSName.FILTER, COSName.get_pdf_name("DCTDecode"))
    stream.set_item(COSName.get_pdf_name("Width"), _cos_int(10))
    stream.set_item(COSName.get_pdf_name("Height"), _cos_int(10))
    stream.set_item(COSName.get_pdf_name("BitsPerComponent"), _cos_int(8))
    stream.set_item(
        COSName.get_pdf_name("ColorSpace"), COSName.get_pdf_name("DeviceRGB")
    )
    stream.set_raw_data(jpeg_bytes)
    image_xobject = PDImageXObject(stream)

    # Register the image on the page and emit a Do for it.
    with PDPageContentStream(doc, page) as cs:
        # PDPageContentStream.draw_image registers + emits the Do.
        cs.draw_image(image_xobject, x=20.0, y=20.0, width=60.0, height=60.0)

    img = PDFRenderer(doc).render_image(0)
    # Centre of the pasted bbox in PIL coords (60 px wide image at PDF
    # (20,20)..(80,80) → PIL y is flipped → 20..80).
    inside = img.getpixel((50, 50))
    assert _is_close(inside, (255, 0, 0), tol=20), inside
    outside = img.getpixel((5, 5))
    assert _is_close(outside, (255, 255, 255)), outside


# ---------------------------------------------------------------------------
# bezier curves
# ---------------------------------------------------------------------------


def test_cubic_bezier_renders_filled_shape() -> None:
    """Path closed via a cubic Bezier — confirm the inside is filled."""
    doc, page = _make_doc(100.0, 100.0)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.5, 0.0)
        # Approximate a circle by 4 cubic Beziers — but we only need one
        # closed shape, so use a teardrop: m, c, l, h, f.
        cs.move_to(50.0, 20.0)
        cs.curve_to(80.0, 20.0, 80.0, 80.0, 50.0, 80.0)
        cs.curve_to(20.0, 80.0, 20.0, 20.0, 50.0, 20.0)
        cs.close_path()
        cs.fill()
    img = PDFRenderer(doc).render_image(0)
    centre = img.getpixel((50, 50))
    assert _is_close(centre, (0, 128, 0), tol=12), centre
    # Far corner should still be white.
    assert _is_close(img.getpixel((5, 5)), (255, 255, 255))


# ---------------------------------------------------------------------------
# colour spaces — gray, cmyk
# ---------------------------------------------------------------------------


def test_gray_and_cmyk_fill_colors_render_correctly() -> None:
    doc, page = _make_doc(100.0, 100.0)
    with PDPageContentStream(doc, page) as cs:
        # Gray 0.5 → mid-grey (~127,127,127)
        cs.set_non_stroking_color_gray(0.5)
        cs.add_rect(10.0, 10.0, 30.0, 30.0)
        cs.fill()
        # CMYK pure cyan (1, 0, 0, 0) → (0, 255, 255)
        cs.set_non_stroking_color_cmyk(1.0, 0.0, 0.0, 0.0)
        cs.add_rect(50.0, 50.0, 30.0, 30.0)
        cs.fill()
    img = PDFRenderer(doc).render_image(0)
    grey_pix = img.getpixel((25, 75))  # PDF (25,25) → PIL (25, 75)
    assert _is_close(grey_pix, (127, 127, 127), tol=5), grey_pix
    cyan_pix = img.getpixel((65, 35))  # PDF (65,65) → PIL (65,35)
    assert _is_close(cyan_pix, (0, 255, 255), tol=5), cyan_pix


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _cos_int(value: int) -> object:
    from pypdfbox.cos import COSInteger

    return COSInteger.get(value)


# ---------------------------------------------------------------------------
# edge cases
# ---------------------------------------------------------------------------


def test_invalid_page_index_raises() -> None:
    doc, _ = _make_doc()
    renderer = PDFRenderer(doc)
    with pytest.raises((IndexError, KeyError)):
        renderer.render_image(99)


# ---------------------------------------------------------------------------
# text rendering — embedded TTF
# ---------------------------------------------------------------------------


def _build_test_ttf() -> bytes:
    """Synthesise a minimal TrueType font with two glyphs (A, B) drawn as
    solid 800x800-em squares. Used by the text-rendering test to confirm
    glyphs land as filled black pixels at the expected page bbox.
    """
    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    fb = FontBuilder(1024, isTTF=True)
    fb.setupGlyphOrder([".notdef", "A", "B"])
    fb.setupCharacterMap({0x41: "A", 0x42: "B"})

    def square_glyph() -> object:
        pen = TTGlyphPen(None)
        pen.moveTo((100, 100))
        pen.lineTo((900, 100))
        pen.lineTo((900, 900))
        pen.lineTo((100, 900))
        pen.closePath()
        return pen.glyph()

    glyphs = {
        ".notdef": TTGlyphPen(None).glyph(),
        "A": square_glyph(),
        "B": square_glyph(),
    }
    fb.setupGlyf(glyphs)
    fb.setupHorizontalMetrics(
        {".notdef": (0, 0), "A": (1024, 0), "B": (1024, 0)}
    )
    fb.setupHorizontalHeader(ascent=900, descent=-100)
    fb.setupNameTable({"familyName": "Test", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, usWinAscent=900, usWinDescent=100)
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _build_ttf_pdfont() -> object:
    """Wrap the synthesised TTF in a PDTrueTypeFont with a /FontDescriptor
    /FontFile2 pointing at the raw bytes."""
    from pypdfbox.cos import COSDictionary, COSName, COSStream
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
    from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont

    ttf_bytes = _build_test_ttf()
    font_file2 = COSStream()
    font_file2.set_raw_data(ttf_bytes)

    fd_dict = COSDictionary()
    descriptor = PDFontDescriptor(fd_dict)
    descriptor.set_font_file2(font_file2)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("TrueType"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("TestFont")
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    # Use WinAnsi-ish encoding — A=0x41, B=0x42 are identity so the default
    # works for our two test glyphs.
    font = PDTrueTypeFont(font_dict)
    return font


def test_ttf_text_show_renders_filled_pixels() -> None:
    """Render BT … Tf … Tj 'AB' ET on a 200x100 page and confirm the
    glyph footprints land as non-white pixels in the expected bbox."""
    doc, page = _make_doc(200.0, 100.0)
    font = _build_ttf_pdfont()
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)  # 50pt = ~50px at 72 DPI
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()
    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 100)
    # Count non-white pixels — synthesised TTF squares are pure black, so
    # the glyph footprint should produce a measurable count of dark pixels.
    dark_count = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if r < 128 and g < 128 and b < 128:
                dark_count += 1
    # Two ~40x40 squares = ~3200 ideal pixels. Allow huge margin for
    # AA softening and glyph metric variance — anything > 200 confirms
    # real rasterisation happened.
    assert dark_count > 200, f"expected glyph fill, got dark_count={dark_count}"


def test_text_without_embedded_font_program_falls_back_quietly() -> None:
    """A Tf for a Standard 14-style font (no /FontFile*) must NOT crash —
    it falls back to a placeholder rectangle and the page still completes.
    """
    from pypdfbox.cos import COSDictionary, COSName
    from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont

    doc, page = _make_doc(100.0, 100.0)
    # Build a TTF font dict with NO /FontDescriptor /FontFile2 — this
    # mimics a Standard 14 reference where no embedded program is shipped.
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("TrueType"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
    )
    font = PDTrueTypeFont(font_dict)

    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 12.0)
        cs.new_line_at_offset(10.0, 50.0)
        cs.show_text("hi")
        cs.end_text()
    # Should not raise.
    img = PDFRenderer(doc).render_image(0)
    assert img.size == (100, 100)


# ---------------------------------------------------------------------------
# Form XObject Do
# ---------------------------------------------------------------------------


def test_form_xobject_do_renders_inner_content() -> None:
    """Place a Form XObject containing a red square at PDF (10..30, 10..30)
    onto a page via Do — the square should appear at PDF (50..70, 50..70)
    after the page-level cm shifts it by (40, 40)."""
    from pypdfbox.cos import COSName, COSStream
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    doc, page = _make_doc(100.0, 100.0)

    # Build a Form XObject with a red 20x20 square at (10, 10)..(30, 30).
    form_stream = COSStream()
    form_stream.set_raw_data(
        b"1 0 0 rg\n"
        b"10 10 20 20 re\n"
        b"f\n"
    )
    form = PDFormXObject(form_stream)
    form.set_b_box(PDRectangle(0.0, 0.0, 100.0, 100.0))

    # Page contents: translate by (40, 40), then Do the form.
    page_dict = page.get_cos_object()
    contents = COSStream()
    contents.set_raw_data(
        b"q\n"
        b"1 0 0 1 40 40 cm\n"
        b"/Form0 Do\n"
        b"Q\n"
    )
    page_dict.set_item(COSName.CONTENTS, contents)
    # Register the form as Form0 in the page resources. PDPage.get_resources()
    # returns a fresh-but-empty PDResources wrapper when none is attached, so
    # always attach explicitly to make sure mutations land on the page.
    from pypdfbox.pdmodel.pd_resources import PDResources

    resources = PDResources()
    page.set_resources(resources)
    resources.put(
        COSName.get_pdf_name("XObject"),
        COSName.get_pdf_name("Form0"),
        form.get_cos_object(),
    )

    img = PDFRenderer(doc).render_image(0)
    # Form-internal rect at PDF (10,10)-(30,30) shifted by (40,40)
    # → PDF (50,50)-(70,70). PIL y is flipped: (50, 30)-(70, 50).
    inside = img.getpixel((60, 40))
    outside_below = img.getpixel((10, 90))
    assert _is_close(inside, (255, 0, 0)), inside
    assert _is_close(outside_below, (255, 255, 255)), outside_below


# ---------------------------------------------------------------------------
# clip path W
# ---------------------------------------------------------------------------


def test_clip_w_restricts_subsequent_fill_to_clip_region() -> None:
    """Clip to a 20x20 box at (40,40), then fill the entire page red.
    Pixels outside the clip should remain white; pixels inside should be
    red.
    """
    from pypdfbox.cos import COSName, COSStream

    doc, page = _make_doc(100.0, 100.0)

    page_dict = page.get_cos_object()
    contents = COSStream()
    contents.set_raw_data(
        b"40 40 20 20 re\n"
        b"W n\n"  # set clip to that rect, then end-path
        b"1 0 0 rg\n"
        b"0 0 100 100 re\n"
        b"f\n"
    )
    page_dict.set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # Inside clip — PDF (50, 50) → PIL (50, 50)
    assert _is_close(img.getpixel((50, 50)), (255, 0, 0)), img.getpixel((50, 50))
    # Outside clip — top-left, bottom-right
    assert _is_close(img.getpixel((10, 10)), (255, 255, 255)), img.getpixel((10, 10))
    assert _is_close(img.getpixel((80, 80)), (255, 255, 255)), img.getpixel((80, 80))


# ---------------------------------------------------------------------------
# inline image BI / ID / EI
# ---------------------------------------------------------------------------


def test_inline_image_renders_pixels() -> None:
    """A 4x4 raw DeviceRGB inline image scaled into a 40x40 area should
    render the expected solid-red pixels.
    """
    from pypdfbox.cos import COSName, COSStream

    doc, page = _make_doc(100.0, 100.0)

    # 4x4 solid red raster, 8 bpc DeviceRGB.
    pixels = bytes([255, 0, 0]) * (4 * 4)
    page_dict = page.get_cos_object()
    contents = COSStream()
    body = (
        b"q\n"
        b"40 0 0 40 30 30 cm\n"
        b"BI\n"
        b"/W 4\n"
        b"/H 4\n"
        b"/CS /RGB\n"
        b"/BPC 8\n"
        b"ID\n"
        + pixels
        + b"\nEI\n"
        b"Q\n"
    )
    contents.set_raw_data(body)
    page_dict.set_item(COSName.CONTENTS, contents)

    img = PDFRenderer(doc).render_image(0)
    # Image bbox is PDF (30, 30)-(70, 70) → PIL (30, 30)-(70, 70).
    inside = img.getpixel((50, 50))
    outside = img.getpixel((5, 5))
    assert _is_close(inside, (255, 0, 0), tol=20), inside
    assert _is_close(outside, (255, 255, 255)), outside
