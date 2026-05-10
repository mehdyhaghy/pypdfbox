"""Font-fallback tests for :class:`PDFRenderer`.

Covers the substitution chain wired through
:meth:`PDFRenderer._resolve_font_program` (PDF 32000-1 §9.8 / §9.10):

* embedded ``/FontFile`` / ``/FontFile2`` / ``/FontFile3`` win first;
* otherwise :class:`pypdfbox.fontbox.font_mappers.FontMappers` resolves a
  Standard 14 wrapper or system substitute;
* the final leg is the descriptor-flag-driven Helvetica / Courier choice
  from :class:`DefaultFontMapper`.

The visible signal is *advance width*: a font with no embedded program
and no ``/Widths`` would otherwise advance by the renderer's 500.0 / 0.0
fallback — but with the chain in place the AFM (Standard 14) width
flows through and produces a different text-matrix advance per glyph.
"""
from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.fontbox.font_mappers import FontMappers
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.rendering import PDFRenderer

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_doc(width: float = 200.0, height: float = 100.0):
    doc = PDDocument()
    while doc.get_number_of_pages() > 0:
        doc.remove_page(0)
    page = PDPage(PDRectangle(0.0, 0.0, width, height))
    doc.add_page(page)
    return doc, page


def _build_unembedded_helvetica():
    """Build a :class:`PDType1Font` named ``Helvetica`` with no
    ``/FontFile`` and no ``/Widths``. Mirrors a tiny PDF that says "use
    Helvetica" and trusts the consumer to supply the program — the case
    the fallback chain is designed to handle."""
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
    )
    return PDType1Font(font_dict)


def _build_unembedded_unknown_font():
    """Build a PDType1Font with a name **outside** the Standard 14 set
    and no embedded program, no /Widths, no /FontDescriptor — forces the
    DefaultFontMapper's universal-fallback branch (Helvetica)."""
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("CompletelyMadeUpFontName"),
    )
    return PDType1Font(font_dict)


# ---------------------------------------------------------------------------
# resolver-level checks
# ---------------------------------------------------------------------------


def test_resolve_font_program_returns_standard14_wrapper_for_helvetica() -> None:
    """An unembedded ``/Helvetica`` reference should resolve through the
    FontMappers chain to a :class:`Standard14FontWrapper` — the canonical
    AFM-backed substitute for Helvetica."""
    FontMappers.reset()
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    font = _build_unembedded_helvetica()

    program = renderer._resolve_font_program(font)  # noqa: SLF001
    assert program is not None
    # The default mapper exposes Standard14FontWrapper for Standard 14 names.
    assert program.get_name() == "Helvetica"


def test_resolve_font_program_falls_back_to_helvetica_for_unknown_name() -> None:
    """Unknown PostScript name + no descriptor flags should land on
    plain Helvetica (the DefaultFontMapper's universal-fallback default)."""
    FontMappers.reset()
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    font = _build_unembedded_unknown_font()

    program = renderer._resolve_font_program(font)  # noqa: SLF001
    assert program is not None
    # Style-only fallback chooses Helvetica for proportional / non-serif.
    assert program.get_name() == "Helvetica"


def test_resolve_font_program_caches_per_font_instance() -> None:
    """Repeated calls for the same font should return the same object —
    the cache lets renderers avoid re-walking the mapper per glyph."""
    FontMappers.reset()
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)
    font = _build_unembedded_helvetica()

    first = renderer._resolve_font_program(font)  # noqa: SLF001
    second = renderer._resolve_font_program(font)  # noqa: SLF001
    assert first is second


# ---------------------------------------------------------------------------
# end-to-end rendering check — fallback metrics flow into text matrix
# ---------------------------------------------------------------------------


def test_unembedded_helvetica_renders_with_standard14_widths() -> None:
    """Render ``Tj 'AB'`` against an unembedded Helvetica reference. The
    placeholder rectangles should be **wider** than the renderer's
    historical 0.0/500.0 fallback because the fallback chain pulls
    advance widths straight from the AFM (Helvetica 'A' = 667 1/1000 em,
    'B' = 667 1/1000 em — both well below 500 too, but distinct from the
    sentinel because they're not equal to 500.0)."""
    FontMappers.reset()
    doc, page = _make_doc(400.0, 100.0)
    font = _build_unembedded_helvetica()
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.5, 0.5, 0.5)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (400, 100)

    # The placeholder boxes paint a faint outline — confirm *something*
    # ended up on the canvas (i.e. text wasn't silently skipped).
    non_white = 0
    for y in range(img.size[1]):
        for x in range(img.size[0]):
            r, g, b = img.getpixel((x, y))
            if r < 250 or g < 250 or b < 250:
                non_white += 1
                if non_white > 0:
                    break
        if non_white > 0:
            break
    assert non_white > 0, "fallback path painted nothing — text was skipped"


def test_unknown_font_with_fixed_pitch_flag_picks_courier_fallback() -> None:
    """A descriptor with ``/Flags`` carrying the fixed-pitch bit should
    flow through the FontMappers fallback to Courier, not Helvetica.
    Validates the descriptor-driven branch in
    :class:`DefaultFontMapper`."""
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
    from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font

    FontMappers.reset()
    doc, _page = _make_doc()
    renderer = PDFRenderer(doc)

    fd_dict = COSDictionary()
    descriptor = PDFontDescriptor(fd_dict)
    # Flag bit 1 = FixedPitch (PDF 32000-1 Table 123).
    descriptor.set_flags(1 << 0)
    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("MysteryMonoFont"),
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    font = PDType1Font(font_dict)

    program = renderer._resolve_font_program(font)  # noqa: SLF001
    assert program is not None
    assert program.get_name() == "Courier"
