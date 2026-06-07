"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/PDPageContentStreamTest.java

Upstream baseline: PDFBox 3.0.x.

Only the producer-side (writer) tests are translated here. Upstream's
test class also exercises the rendering side (PDFRenderer round-trips,
TIFF byte equivalence) — those belong to the rendering test suite
(``tests/rendering/``) and are skipped here.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.pd_page_content_stream import (
    AppendMode,
    PDPageContentStream,
)

_CONTENTS: COSName = COSName.CONTENTS  # type: ignore[attr-defined]


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))  # US Letter, upstream default
    doc.add_page(page)
    return page


def _stream_bytes(page: PDPage) -> bytes:
    return page.get_contents()


# ----------------------------------------------------------------------
# port: testSetCmykColors() — assert that K/k operators are emitted with
# four CMYK component operands.
# ----------------------------------------------------------------------


def test_set_cmyk_colors() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.set_stroking_color(0.1, 0.2, 0.3, 0.4)
        cs.set_non_stroking_color(0.5, 0.6, 0.7, 0.8)
    body = _stream_bytes(page)
    assert b"0.1 0.2 0.3 0.4 K" in body
    assert b"0.5 0.6 0.7 0.8 k" in body


# ----------------------------------------------------------------------
# port: testRectCommandWithNegatives() — the rectangle command must
# round-trip negative width/height components verbatim.
# ----------------------------------------------------------------------


def test_rect_command_with_negatives() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(10, 20, -5, -7)
    assert _stream_bytes(page) == b"10 20 -5 -7 re\n"


# ----------------------------------------------------------------------
# port: testCloseContentStream() — closing a content stream twice is
# idempotent and the second close is a no-op.
# ----------------------------------------------------------------------


def test_close_content_stream() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    cs = PDPageContentStream(doc, page)
    cs.move_to(0, 0)
    cs.close()
    cs.close()  # second close should not raise nor duplicate writes
    assert _stream_bytes(page) == b"0 0 m\n"


# ----------------------------------------------------------------------
# port: testTextStateOperators() — Tc, Tw, Tz, TL, Ts, Tr round-trip.
# ----------------------------------------------------------------------


def test_text_state_operators() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_character_spacing(1.5)
        cs.set_word_spacing(2.5)
        cs.set_horizontal_scaling(80)
        cs.set_leading(14)
        cs.set_text_rise(1)
        cs.set_text_rendering_mode(0)
        cs.end_text()
    body = _stream_bytes(page)
    assert b"1.5 Tc" in body
    assert b"2.5 Tw" in body
    assert b"80 Tz" in body
    assert b"14 TL" in body
    assert b"1 Ts" in body
    assert b"0 Tr" in body


# ----------------------------------------------------------------------
# port: testGraphicsStateOperators() — q/Q/cm round-trip.
# ----------------------------------------------------------------------


def test_graphics_state_operators() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.save_graphics_state()
        cs.transform(2, 0, 0, 2, 0, 0)
        cs.restore_graphics_state()
    assert _stream_bytes(page) == b"q\n2 0 0 2 0 0 cm\nQ\n"


# ----------------------------------------------------------------------
# port: testPathPainting() — m/l/h/c/S/f/B all emit the canonical
# single/double-byte operators.
# ----------------------------------------------------------------------


def test_path_painting_operators() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.move_to(0, 0)
        cs.line_to(10, 0)
        cs.curve_to(15, 5, 15, 10, 10, 10)
        cs.close_path()
        cs.stroke()
    assert _stream_bytes(page) == (
        b"0 0 m\n10 0 l\n15 5 15 10 10 10 c\nh\nS\n"
    )


# ----------------------------------------------------------------------
# port: testFillEvenOddAndClipEvenOdd() — even-odd painting and
# clipping operators.
# ----------------------------------------------------------------------


def test_fill_even_odd_and_clip_even_odd() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(0, 0, 10, 10)
        cs.fill_even_odd()
        cs.add_rect(0, 0, 20, 20)
        cs.clip_even_odd()
    body = _stream_bytes(page)
    assert b"f*" in body
    assert b"W*\nn\n" in body


# ----------------------------------------------------------------------
# port: testEndPath() — the n operator alone.
# ----------------------------------------------------------------------


def test_end_path_emits_n() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.add_rect(1, 2, 3, 4)
        cs.end_path()
    assert _stream_bytes(page) == b"1 2 3 4 re\nn\n"


# ----------------------------------------------------------------------
# port: testSetTextMatrix() — Tm with a 6-component matrix.
# ----------------------------------------------------------------------


def test_set_text_matrix() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_text_matrix(1, 0, 0, 1, 50, 750)
        cs.end_text()
    assert b"1 0 0 1 50 750 Tm" in _stream_bytes(page)


# ----------------------------------------------------------------------
# port: testShowText() — BT / Tf / Tj / ET sequence.
# ----------------------------------------------------------------------


def test_show_text_round_trip() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(50, 750)
        cs.show_text("Hello World")
        cs.end_text()
    body = _stream_bytes(page)
    assert body == (
        b"BT\n/F1 12 Tf\n50 750 Td\n(Hello World) Tj\nET\n"
    )


# ----------------------------------------------------------------------
# port: testAppendModePreservesExistingContents() — APPEND must promote
# a single existing /Contents stream to a COSArray and append the new
# stream after it.
# ----------------------------------------------------------------------


def test_append_mode_preserves_existing_contents() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    initial = COSStream()
    initial.set_raw_data(b"q\nQ\n")
    page.set_contents(initial)

    with PDPageContentStream(doc, page, AppendMode.APPEND) as cs:
        cs.move_to(0, 0)

    contents = page.get_cos_object().get_dictionary_object(_CONTENTS)
    assert isinstance(contents, COSArray)
    assert contents.size() == 2
    assert contents.get(0) is initial


# ----------------------------------------------------------------------
# Rendering round-trip — upstream uses PDFRenderer + TIFF byte-equivalence
# against a Java-rendered model image. We can't byte-match Java's raster
# output, but we can verify the *structural* round-trip: a content stream
# emitted via PDPageContentStream must survive parse → PDFRenderer.render
# and produce a non-blank raster of the correct dimensions. The pixel-
# parity portion stays out of scope (different rasteriser → different
# byte output) — that's tracked separately in CHANGES.md.
# ----------------------------------------------------------------------


def test_rendering_round_trip() -> None:
    """Structural round-trip: a page written through PDPageContentStream
    must render via PDFRenderer to an image of the page's pixel size and
    contain at least one non-background pixel (so we know the content
    stream actually reached the rasteriser).

    Upstream's variant of this test compared the raster against a stored
    TIFF model — that byte-exact comparison isn't achievable across the
    Java/Python rasteriser boundary and is intentionally not ported.
    """
    # Import lazily so the rendering import only happens when this test
    # actually runs (matches PDFRenderer's own lazy contentstream import).
    from pypdfbox.rendering import PDFRenderer  # noqa: PLC0415

    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, 100.0, 50.0))
    doc.add_page(page)
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color(0.5, 0.5, 0.5)
        cs.add_rect(10.0, 10.0, 30.0, 30.0)
        cs.fill()

    renderer = PDFRenderer(doc)
    image = renderer.render_image(0)
    assert image is not None
    # 1pt = 1px at scale=1.0 (72 DPI base * 1.0).
    assert image.size == (100, 50)
    # Non-blank: the filled grey rect must produce *some* non-(255,255,255)
    # pixels. We don't pin the exact colour — that's pixel-parity, out of
    # scope for the structural test.
    extrema = image.getextrema()
    assert any(channel_min < 255 for channel_min, _ in extrema), (
        "renderer produced an all-white canvas — content stream not reaching "
        "the rasteriser"
    )
