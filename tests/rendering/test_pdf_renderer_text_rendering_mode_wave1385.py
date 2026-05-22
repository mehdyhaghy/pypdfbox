"""Wave 1385 — PDF text rendering mode (``Tr``) renderer dispatch.

Before wave 1385 the ``Tr`` operator was registered as a parser scaffold
only — the renderer's ``_DISPATCH`` table had no entry for it, so the
operand was silently consumed without affecting the graphics state. As a
result every glyph painted as if mode 0 (fill) regardless of the upstream
file's intent, breaking:

* mode 1 / 2 / 5 / 6 — strokeable outline text (logos, large headings);
* mode 3 / 7 — invisible OCR layers (PDFs from Tesseract / Adobe scans
  where glyph metrics are embedded for text extraction but the visual
  content is the rasterised page below);
* mode 4-7 — text-as-clip (used by decorative drop-cap / pattern-text
  effects).

Wave 1385 wires the ``Tr`` operator into the renderer's text-state, then
routes ``_paint_glyph_path`` through a mode-aware dispatcher
(fill / stroke / fill+stroke / invisible / clip variants).
"""

from __future__ import annotations

import io

from pypdfbox.cos import (
    COSDictionary,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer


def _make_doc(width: float = 100.0, height: float = 100.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _build_square_ttf_bytes() -> bytes:
    """Synthesise a TrueType font where glyphs ``A`` and ``B`` are drawn
    as solid 800×800-em squares — the same helper used in
    ``test_pdf_renderer_text.py``.
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
    fb.setupNameTable({"familyName": "DejaVuSquare", "styleName": "Regular"})
    fb.setupOS2(sTypoAscender=900, usWinAscent=900, usWinDescent=100)
    fb.setupPost()
    buf = io.BytesIO()
    fb.save(buf)
    return buf.getvalue()


def _wrap_ttf(ttf_bytes: bytes):
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
    from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont

    font_file2 = COSStream()
    font_file2.set_raw_data(ttf_bytes)

    fd_dict = COSDictionary()
    descriptor = PDFontDescriptor(fd_dict)
    descriptor.set_font_file2(font_file2)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("TrueType"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("DejaVuSquare")
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    return PDTrueTypeFont(font_dict)


def _count_dark_pixels(img) -> int:
    dark = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if r < 128 and g < 128 and b < 128:
                dark += 1
    return dark


def _count_red_pixels(img) -> int:
    """Pixels that are saturated red (stroke colour in tests below)."""
    red = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if r > 200 and g < 80 and b < 80:
                red += 1
    return red


# ---------------------------------------------------------------------------
# Tr operator → renderer GS plumb-through
# ---------------------------------------------------------------------------


def test_tr_operator_sets_text_rendering_mode_on_gs() -> None:
    """Smoke test — the ``Tr`` operator dispatches through
    ``_op_set_text_rendering_mode`` and updates the active GS field."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    from pypdfbox.rendering.pdf_renderer import _GState

    renderer._gs_stack = [_GState()]
    from pypdfbox.cos import COSInteger

    renderer._op_set_text_rendering_mode(None, [COSInteger.get(3)])
    assert renderer._gs.text_rendering_mode == 3


def test_tr_operator_clamps_out_of_range_modes() -> None:
    """Modes outside 0..7 clamp to the boundary."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    from pypdfbox.rendering.pdf_renderer import _GState

    renderer._gs_stack = [_GState()]
    from pypdfbox.cos import COSInteger

    renderer._op_set_text_rendering_mode(None, [COSInteger.get(99)])
    assert renderer._gs.text_rendering_mode == 7
    renderer._op_set_text_rendering_mode(None, [COSInteger.get(-5)])
    assert renderer._gs.text_rendering_mode == 0


def test_tr_operator_is_registered_in_dispatch() -> None:
    """``Tr`` resolves to its handler in the renderer's dispatch table."""
    from pypdfbox.rendering.pdf_renderer import _DISPATCH

    assert "Tr" in _DISPATCH
    assert _DISPATCH["Tr"] is PDFRenderer._op_set_text_rendering_mode


# ---------------------------------------------------------------------------
# Visible / invisible modes against rasterised TTF text
# ---------------------------------------------------------------------------


def test_text_rendering_mode_0_paints_filled_glyphs() -> None:
    """Mode 0 (default) — fill. Glyphs should plant filled black pixels."""
    doc, page = _make_doc(200.0, 100.0)
    font = _wrap_ttf(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.set_text_rendering_mode(0)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()
    img = PDFRenderer(doc).render_image(0)
    dark = _count_dark_pixels(img)
    assert dark > 200, f"mode 0 should paint filled glyphs; dark={dark}"


def test_text_rendering_mode_3_paints_nothing() -> None:
    """Mode 3 (invisible) — no paint should reach the canvas. Used by
    OCR layers in scanned PDFs."""
    doc, page = _make_doc(200.0, 100.0)
    font = _wrap_ttf(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.set_text_rendering_mode(3)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()
    img = PDFRenderer(doc).render_image(0)
    dark = _count_dark_pixels(img)
    assert dark == 0, (
        f"mode 3 (invisible) must not paint; dark={dark}"
    )


def test_text_rendering_mode_1_strokes_glyphs_in_stroke_color() -> None:
    """Mode 1 (stroke only) — paints the outline in the *stroking* colour
    with no fill. Used by decorative outline-only headings."""
    doc, page = _make_doc(200.0, 100.0)
    font = _wrap_ttf(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        # Distinct stroke (red) vs. non-stroke (black) colours so we can
        # tell the difference between fill and stroke paths.
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.set_stroking_color_rgb(1.0, 0.0, 0.0)
        cs.set_line_width(2.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.set_text_rendering_mode(1)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()
    img = PDFRenderer(doc).render_image(0)
    red = _count_red_pixels(img)
    dark = _count_dark_pixels(img)
    # Mode 1 paints stroke only — we should see red outline pixels and
    # NO dark (non-stroke-colour fill) pixels.
    assert red > 0, f"mode 1 should paint a red outline; red={red}"
    assert dark == 0, f"mode 1 must not fill; dark={dark}"


def test_text_rendering_mode_2_fills_and_strokes() -> None:
    """Mode 2 (fill + stroke) — both the non-stroking fill and the
    stroking outline land on the canvas."""
    doc, page = _make_doc(200.0, 100.0)
    font = _wrap_ttf(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.set_stroking_color_rgb(1.0, 0.0, 0.0)
        cs.set_line_width(2.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.set_text_rendering_mode(2)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()
    img = PDFRenderer(doc).render_image(0)
    red = _count_red_pixels(img)
    dark = _count_dark_pixels(img)
    # Both colours present: red on the outline, black under the fill.
    assert red > 0, f"mode 2 should paint a red outline; red={red}"
    assert dark > 0, f"mode 2 should paint a black fill; dark={dark}"


def test_text_rendering_mode_7_clip_only_is_invisible_but_clips_subsequent_paints() -> None:
    """Mode 7 (add to clipping path only) paints no glyph pixels and
    establishes a clip at ET that subsequent fills are intersected with.

    Setup: draw a glyph in mode 7 in the upper-left, then end text and
    fill a big black rectangle across the whole page. Only the area
    inside the glyph clip should darken.
    """
    doc, page = _make_doc(200.0, 100.0)
    font = _wrap_ttf(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.set_text_rendering_mode(7)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()
        # Now fill the whole page — the clip from the text mode 7 above
        # should restrict the fill to the glyph footprint.
        cs.add_rect(0.0, 0.0, 200.0, 100.0)
        cs.fill()

    img = PDFRenderer(doc).render_image(0)
    dark = _count_dark_pixels(img)
    # The clip restricts the fill — the page is not fully black.
    # Some dark pixels should appear inside the glyph footprint.
    total_pixels = img.size[0] * img.size[1]
    assert dark > 0, "mode-7 clip should let SOME glyph-shaped fill through"
    # Without the clip the fill would have darkened ~20000 pixels;
    # with the glyph clip we expect well under half that. (Glyphs are
    # 50pt squares × 2 = ~5000 pixels nominal.)
    assert dark < total_pixels // 2, (
        f"mode 7 clip should restrict fill to glyph area; "
        f"dark={dark}/{total_pixels}"
    )


def test_text_rendering_mode_4_fills_and_clips() -> None:
    """Mode 4 (fill + add to clipping path) — paints the glyph AND
    accumulates the outline for the post-ET clip."""
    doc, page = _make_doc(200.0, 100.0)
    font = _wrap_ttf(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.set_text_rendering_mode(4)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()
        # Then attempt to fill the entire page with a different colour —
        # only the clipped glyph area should pick it up.
        cs.set_non_stroking_color_rgb(1.0, 0.0, 0.0)
        cs.add_rect(0.0, 0.0, 200.0, 100.0)
        cs.fill()

    img = PDFRenderer(doc).render_image(0)
    red = _count_red_pixels(img)
    # Some red bleeds through inside the glyph clip; the rest of the
    # page stays white.
    assert red > 0, "mode 4 should fill AND establish a clip for subsequent paints"
    total_pixels = img.size[0] * img.size[1]
    assert red < total_pixels // 2, (
        "mode-4 clip should restrict the post-fill to the glyph area"
    )


def test_bt_resets_text_clip_accumulator() -> None:
    """Each BT starts a fresh text-clip accumulator — clip paths from a
    prior BT/ET shouldn't bleed into the next one (PDF 32000-1 §9.3.6
    says the clip update happens "at the end of the text object that
    initiated it")."""
    renderer = PDFRenderer.__new__(PDFRenderer)
    from pypdfbox.rendering.pdf_renderer import _GState

    renderer._gs_stack = [_GState()]
    renderer._image = None  # _op_end_text short-circuits on None image
    renderer._text_clip_paths = ["bogus-prior-entry"]
    renderer._op_begin_text(None, [])
    assert renderer._text_clip_paths == []
