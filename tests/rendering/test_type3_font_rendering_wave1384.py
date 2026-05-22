"""Wave 1384 — Type 3 font rendering close-the-gap tests.

Anchors the rendering surface promises around the wave-1384 doc-string
revision (no more "deferred placeholder rectangle") and the d0/d1
operator dispatch + bbox-clipping implementation:

1. A Type 3 glyph whose charproc paints a filled square via the
   ``m l l l h f`` path-construction operators (instead of ``re``)
   lands on the page at the expected pixel coordinates.
2. A page that shows the same Type 3 glyph multiple times paints
   non-overlapping instances at distinct positions — exercises the
   per-glyph charproc dispatch + advance arithmetic.
3. A ``d1`` glyph whose painted geometry would *exceed* its declared
   bbox is clipped to the bbox — no stray pixels bleed outside.

The synthetic Type 3 fonts here are constructed inline (no fixture
files) so the assertions don't depend on any external glyph outline
program — the charproc bytes are the spec.
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


def _make_doc(
    width: float = 200.0, height: float = 100.0,
) -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _build_font(
    *,
    charproc_bytes: bytes,
    glyph_name: str = "A",
    code: int = 0x41,
    width: int = 600,
    font_matrix: tuple[float, float, float, float, float, float] = (
        0.001, 0.0, 0.0, 0.001, 0.0, 0.0,
    ),
) -> PDType3Font:
    """Minimal one-glyph Type 3 font builder. The charproc bytes are
    used verbatim; the encoding maps ``code`` → ``glyph_name``."""
    cp_stream = COSStream()
    cp_stream.set_raw_data(charproc_bytes)
    char_procs = COSDictionary()
    char_procs.set_item(COSName.get_pdf_name(glyph_name), cp_stream)

    differences = COSArray()
    differences.add(COSInteger.get(code))
    differences.add(COSName.get_pdf_name(glyph_name))
    encoding_dict = COSDictionary()
    encoding_dict.set_item(
        COSName.get_pdf_name("Differences"), differences,
    )

    widths_arr = COSArray()
    widths_arr.add(COSInteger.get(width))

    font_bbox = COSArray()
    for v in (0, 0, 1000, 1000):
        font_bbox.add(COSInteger.get(v))

    font_matrix_arr = COSArray()
    for v in font_matrix:
        font_matrix_arr.add(COSFloat(float(v)))

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    font_dict.set_item(COSName.get_pdf_name("FontBBox"), font_bbox)
    font_dict.set_item(COSName.get_pdf_name("FontMatrix"), font_matrix_arr)
    font_dict.set_item(COSName.get_pdf_name("CharProcs"), char_procs)
    font_dict.set_item(COSName.get_pdf_name("Encoding"), encoding_dict)
    font_dict.set_int(COSName.get_pdf_name("FirstChar"), code)
    font_dict.set_int(COSName.get_pdf_name("LastChar"), code)
    font_dict.set_item(COSName.get_pdf_name("Widths"), widths_arr)
    return PDType3Font(font_dict)


def _count_dark_pixels(img, threshold: int = 128) -> int:
    """Count pixels darker than ``threshold`` in all RGB channels."""
    dark = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if r < threshold and g < threshold and b < threshold:
                dark += 1
    return dark


def _has_dark_in_region(img, box: tuple[int, int, int, int]) -> bool:
    cropped = img.crop(box)
    return _count_dark_pixels(cropped) > 0


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_type3_filled_square_via_m_l_h_f_paints_pixels() -> None:
    """Filled square drawn by ``m l l l h f`` (NOT ``re f``) — exercises
    the path-construction op set on a Type 3 charproc end-to-end and
    confirms the brief's reference geometry produces dark pixels."""
    # Square at glyph (100, 100) -> (200, 200) — 100-unit side in glyph
    # space. After /FontMatrix [0.001, 0, 0, 0.001, 0, 0] the square is
    # 0.1 em wide; at 100pt font size the square is 10 page units.
    charproc_bytes = (
        b"100 100 m\n200 100 l\n200 200 l\n100 200 l\nh\nf\n"
    )
    doc, page = _make_doc(200.0, 100.0)
    font = _build_font(charproc_bytes=charproc_bytes)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 100.0)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text(b"A")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 100)
    dark = _count_dark_pixels(img)
    # Square is ~10x10 page units at 100pt -> ~100 dark pixels nominal.
    # Generous slack for anti-aliasing.
    assert dark > 30, (
        f"expected Type 3 m/l/h/f square to paint pixels, got {dark}"
    )
    # The square sits at user-space (~30, 40) -> (~40, 50). After the
    # PIL y-flip in a 100-px-tall image that lands at roughly
    # (30, 50) -> (40, 60). Bottom-right corner stays clean.
    assert not _has_dark_in_region(img, (150, 70, 200, 100))


def test_type3_multi_glyph_paints_distinct_positions() -> None:
    """A multi-glyph run (``AAA``) of the same Type 3 charproc must paint
    at three distinct page positions, with the advance arithmetic
    spreading the rectangles out. The first and last rectangles must
    each carry their own dark pixels."""
    # Rectangle in glyph (100, 0) -> (700, 700); 50pt font + /Widths=900
    # gives ~45 user-unit advance per glyph (well clear of the ~30-unit
    # rect width).
    charproc_bytes = b"100 0 600 700 re\nf\n"
    doc, page = _make_doc(300.0, 100.0)
    font = _build_font(charproc_bytes=charproc_bytes, width=900)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.new_line_at_offset(10.0, 30.0)
        cs.show_text(b"AAA")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (300, 100)
    # First glyph lands around x=15-50, second around x=60-95, third
    # around x=105-140. Sample one column from each: each MUST have at
    # least one dark pixel.
    assert _has_dark_in_region(img, (15, 30, 50, 70)), (
        "expected first Type 3 glyph in (15, 30)-(50, 70)"
    )
    assert _has_dark_in_region(img, (60, 30, 95, 70)), (
        "expected second Type 3 glyph in (60, 30)-(95, 70)"
    )
    assert _has_dark_in_region(img, (105, 30, 140, 70)), (
        "expected third Type 3 glyph in (105, 30)-(140, 70)"
    )


def test_type3_d1_bbox_clips_overpaint() -> None:
    """``d1 wx wy llx lly urx ury`` declares a glyph bbox. Per PDF
    32000-1 §9.6.5.3 any paint outside this bbox is implementation-
    defined; PDFBox treats the bbox as a clip. Wave 1384 mirrors that:
    a charproc whose painted geometry runs PAST the declared bbox
    must NOT bleed pixels outside.

    Setup: bbox in glyph space is (0, 0) -> (500, 500), but the
    rectangle painted is (0, 0) -> (1000, 1000). Pixels in the
    glyph-space band (500, 0) -> (1000, 1000) should be clipped away."""
    # bbox: 0 0 500 500, then a filled rectangle covering the FULL
    # glyph-em (0, 0) -> (1000, 1000). Only the lower-left quadrant
    # (0, 0) -> (500, 500) should survive.
    charproc_bytes = (
        b"600 0 0 0 500 500 d1\n"
        b"0 0 1000 1000 re\n"
        b"f\n"
    )
    doc, page = _make_doc(200.0, 200.0)
    font = _build_font(charproc_bytes=charproc_bytes)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 100.0)
        # Place the glyph at user-space (50, 50). With /FontMatrix
        # 0.001 and font_size 100, glyph-space unit -> 0.1 user units,
        # so the bbox-clipped region (0, 0) -> (500, 500) covers user
        # (50, 50) -> (100, 100); the unclipped overpaint would be
        # (50, 50) -> (150, 150).
        cs.new_line_at_offset(50.0, 50.0)
        cs.show_text(b"A")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 200)
    # The clipped (visible) region in PIL coords (y-flip from PDF):
    # PDF (50, 50) -> (100, 100) becomes PIL (50, 100) -> (100, 150).
    # MUST have dark pixels.
    visible = img.crop((50, 100, 100, 150))
    assert _count_dark_pixels(visible) > 50, (
        "expected dark pixels inside the d1 bbox region"
    )
    # The would-be-overpainted region (PDF (100, 100) -> (150, 150))
    # in PIL coords is (100, 50) -> (150, 100). Wave 1384 clips this,
    # so there must be NO dark pixels there.
    bled = img.crop((110, 60, 150, 95))
    bled_dark = _count_dark_pixels(bled)
    assert bled_dark == 0, (
        f"d1 bbox clip failed: overpainted region carries {bled_dark} "
        f"dark pixels"
    )


def test_type3_glyph_paints_at_expected_position() -> None:
    """Structural pixel-sample test: the glyph must land at the
    expected position and NOT at a known-absent position. The brief's
    ask: non-zero pixel sample at expected location, zero pixel sample
    at expected-absent location."""
    # Rectangle (100, 100) -> (200, 200) in glyph space — 100x100 unit
    # square. At 100pt font + 0.001 FontMatrix the square is 10x10
    # user-space units. Place at user (50, 50) so square lives at
    # user (60, 60) -> (70, 70).
    charproc_bytes = (
        b"100 100 m\n200 100 l\n200 200 l\n100 200 l\nh\nf\n"
    )
    doc, page = _make_doc(200.0, 200.0)
    font = _build_font(charproc_bytes=charproc_bytes)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 100.0)
        cs.new_line_at_offset(50.0, 50.0)
        cs.show_text(b"A")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 200)

    # PIL y-flip of a 200-px-tall image: PDF y=60 becomes PIL y=140.
    # The painted square in PIL coords is roughly (60, 130) -> (70, 140).
    inside = img.crop((60, 130, 70, 140))
    assert _count_dark_pixels(inside) > 0, (
        "expected dark pixels at the Type 3 glyph's painted box"
    )

    # Far away (top-right corner) is verified clean — the glyph cannot
    # reach there. Brief: "zero pixel sample at expected absent location".
    absent = img.crop((150, 5, 195, 50))
    assert _count_dark_pixels(absent) == 0, (
        "Type 3 glyph leaked dark pixels into a known-absent region"
    )


def test_type3_d1_advance_override_takes_precedence_over_widths() -> None:
    """``d1`` declares its own advance — PDFBox uses that in preference
    to the font's ``/Widths`` value. Wave 1384 mirrors this: the
    second of two glyph shows is positioned by the d1 width, not the
    /Widths value.

    Setup: /Widths=200, but d1 declares wx=900. Two glyph shows in a
    row should leave a clear gap between them (wx=900 in 1/1000-em ->
    0.9 em -> 27 user units at 30pt), not overlap (which Widths=200
    would imply -> 6 user units, way less than the rect width).
    """
    # bbox (0, 0)-(1000, 1000) is wide enough to enclose the rect.
    charproc_bytes = (
        b"900 0 0 0 1000 1000 d1\n"
        b"100 0 600 700 re\n"
        b"f\n"
    )
    doc, page = _make_doc(200.0, 100.0)
    font = _build_font(charproc_bytes=charproc_bytes, width=200)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 30.0)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text(b"AA")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 100)
    dark = _count_dark_pixels(img)
    # Two non-overlapping rectangles → at least 2x the single-glyph
    # painted area. A single rect at this size is ~18x21 = ~400 dark
    # pixels (with anti-aliasing slack); two overlap by some amount
    # but still > 400.
    assert dark > 400, (
        f"expected two distinct Type 3 glyphs widening via d1, got {dark}"
    )
