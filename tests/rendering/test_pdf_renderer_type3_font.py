"""Type 3 font (charproc) rendering tests for :class:`PDFRenderer`.

Type 3 fonts are PDF's "draw the glyph yourself" font kind: each glyph is
a content stream that runs through the same operator dispatch as a Form
XObject, only scaled into text space via /FontMatrix. We synthesise a
minimal Type 3 font with one glyph (a black rectangle), drop it onto a
page, and assert the renderer paints the expected pixels.

Distinct from :mod:`tests.rendering.test_pdf_renderer_text` which
exercises TTF / Type1 / Type1C / Type0 paths — those rely on embedded
glyph programs and fontTools-driven outline extraction. The Type 3 path
is wholly engine-driven (no fontTools, no aggdraw glyph pen) so it gets
its own focused regression file.
"""
from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_doc(width: float = 100.0, height: float = 100.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _make_type3_font_one_rect(
    glyph_name: str = "A",
    code: int = 0x41,
    width: int = 600,
) -> PDType3Font:
    """Build a Type 3 font carrying one charproc that paints a filled
    rectangle in glyph space.

    Glyph-space layout (default /FontMatrix = [0.001, 0, 0, 0.001, 0, 0]):
    the rectangle covers (100, 0) -> (700, 700) in glyph units, i.e.
    (0.1, 0.0) -> (0.7, 0.7) in 1-em text space — enough to drop a
    visible block at any practical font size. The painting op is ``f``
    which fills with the surrounding non-stroking colour.
    """
    # Charproc: ``100 0 600 700 re f`` (rectangle then non-zero fill).
    charproc_bytes = b"100 0 600 700 re\nf\n"
    charproc_stream = COSStream()
    charproc_stream.set_raw_data(charproc_bytes)

    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name(glyph_name), charproc_stream)

    # /Encoding: /Differences with code -> glyph_name, so the renderer's
    # encoding lookup resolves ``code`` to ``glyph_name`` and finds the
    # matching charproc.
    differences = COSArray()
    differences.add(COSInteger.get(code))
    differences.add(COSName.get_pdf_name(glyph_name))
    encoding_dict = COSDictionary()
    encoding_dict.set_item(
        COSName.get_pdf_name("Differences"), differences
    )

    # /Widths covers FirstChar..LastChar inclusive. Single-glyph font:
    # FirstChar = LastChar = code, /Widths is a one-element array.
    widths = COSArray()
    widths.add(COSInteger.get(width))

    # /FontBBox in glyph-space units — bounds of the rectangle.
    font_bbox = COSArray()
    for v in (0, 0, 1000, 1000):
        font_bbox.add(COSInteger.get(v))

    # /FontMatrix = default [0.001, 0, 0, 0.001, 0, 0].
    font_matrix = COSArray()
    for v in (0.001, 0.0, 0.0, 0.001, 0.0, 0.0):
        font_matrix.add(COSFloat(v))

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    font_dict.set_item(COSName.get_pdf_name("FontBBox"), font_bbox)
    font_dict.set_item(COSName.get_pdf_name("FontMatrix"), font_matrix)
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), encoding_dict)
    font_dict.set_int(COSName.get_pdf_name("FirstChar"), code)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), code)
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths)

    return PDType3Font(font_dict)


def _count_dark_pixels(img) -> int:
    dark = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if r < 128 and g < 128 and b < 128:
                dark += 1
    return dark


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_type3_charproc_renders_filled_rectangle() -> None:
    """A Type 3 font whose only glyph is a filled rectangle must paint
    visible black pixels in the expected page region when shown via
    ``Tj``. Regression guard against the pre-Type-3-renderer fallback
    (which silently dropped the glyph)."""
    doc, page = _make_doc(200.0, 100.0)
    font = _make_type3_font_one_rect(glyph_name="A", code=0x41)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text(b"A")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 100)
    dark = _count_dark_pixels(img)
    # The rectangle is ~0.6 em wide x 0.7 em tall at 50pt -> ~30x35 px.
    # That's ~1000 dark pixels nominally; allow generous slack for AA.
    assert dark > 200, f"expected Type 3 glyph rectangle, got dark={dark}"

    # The rectangle sits near the BT origin (20, 30) → in PDF user space
    # the glyph spans roughly (25, 30) -> (55, 65), which after the y-flip
    # to 100-px-tall PIL coords lands roughly at (25, 35) -> (55, 70).
    # The bottom-right corner (150, 70, 200, 100) must stay clean.
    bottom_right = img.crop((150, 70, 200, 100))
    assert _count_dark_pixels(bottom_right) == 0


def test_type3_glyph_advance_translates_following_glyphs() -> None:
    """Two glyph runs of the same Type 3 font should paint two
    non-overlapping rectangles, with the second offset by /Widths in
    1/1000-em units. Confirms the advance formula folds /FontMatrix and
    /Widths together correctly."""
    doc, page = _make_doc(200.0, 100.0)
    # Use a wide /Widths value so the second glyph is clearly displaced.
    font = _make_type3_font_one_rect(glyph_name="A", code=0x41, width=800)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 30.0)
        cs.new_line_at_offset(20.0, 50.0)
        cs.show_text(b"AA")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    dark_total = _count_dark_pixels(img)

    # Single-glyph baseline.
    doc1, page1 = _make_doc(200.0, 100.0)
    font1 = _make_type3_font_one_rect(glyph_name="A", code=0x41, width=800)
    with PDPageContentStream(doc1, page1) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font1, 30.0)
        cs.new_line_at_offset(20.0, 50.0)
        cs.show_text(b"A")
        cs.end_text()
    img1 = PDFRenderer(doc1).render_image(0)
    dark_one = _count_dark_pixels(img1)

    # Two glyphs should leave nearly 2x the painted footprint of one
    # glyph. The advance moved the second rectangle clear of the first
    # (width=800 1/1000-em, font-size=30 → ~24 user-space units of
    # advance, well past the rectangle's ~18-unit width at that size).
    assert dark_total > dark_one + 100, (
        f"two Type 3 glyphs should paint more than one; "
        f"one={dark_one} two={dark_total}"
    )


def test_type3_missing_charproc_is_silent() -> None:
    """Bytes that don't resolve to a /CharProcs entry must not crash and
    must not paint anything — they simply advance past their nominal
    width. Models the real-world ``.notdef``-without-glyph case."""
    doc, page = _make_doc(100.0, 50.0)
    font = _make_type3_font_one_rect(glyph_name="A", code=0x41)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 20.0)
        cs.new_line_at_offset(10.0, 20.0)
        # 0x42 is not in /Encoding /Differences and not in /CharProcs —
        # the renderer should resolve to .notdef, find no charproc, and
        # silently skip painting (no crash, no exception).
        cs.show_text(b"B")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (100, 50)
    # Empty content stream had no painting ops, so the image must be
    # all-white (no dark pixels).
    assert _count_dark_pixels(img) == 0
