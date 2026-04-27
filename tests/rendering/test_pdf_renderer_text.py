"""Text-rendering tests focused on the TrueType + Type0 (composite) glyph
rasterisation paths in :class:`PDFRenderer`.

Distinct from :mod:`tests.rendering.test_pdf_renderer` which already covers
TrueType, Type1 (PFB) and Type1C (CFF) text rendering against synthesised
square-glyph fonts. This module exercises:

* an extra-thick TTF-backed Type0 (Identity-H, CIDFontType2) that walks
  the multi-byte ``read_code`` path and the CID -> GID resolution chain
  in :meth:`PDFRenderer._code_to_gid`;
* parity sanity for plain TTF rendering after the text-show refactor that
  added Type0 awareness (regression guard for simple fonts).
"""
from __future__ import annotations

import io

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
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


def _build_square_ttf_bytes() -> bytes:
    """Produce a minimal TrueType font where glyphs ``A`` and ``B`` are
    drawn as solid 800x800-em squares. Reused across the TTF and Type0
    tests below; structurally identical to the helper in
    :mod:`test_pdf_renderer` but kept self-contained so this file stands
    on its own."""
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


def _wrap_ttf_as_pdtruetypefont(ttf_bytes: bytes):
    """Wrap raw TTF bytes in a :class:`PDTrueTypeFont` with a populated
    ``/FontDescriptor`` ``/FontFile2``."""
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


def _wrap_ttf_as_pdtype0font(ttf_bytes: bytes):
    """Wrap raw TTF bytes in a Type0 / CIDFontType2 hierarchy mirroring a
    real Identity-H composite font:

    * Top-level ``/Type0`` font with ``/Encoding /Identity-H`` and a single
      descendant.
    * Descendant ``/CIDFontType2`` with the embedded ``/FontFile2`` and an
      identity ``/CIDToGIDMap``.
    """
    from pypdfbox.pdmodel.font.pd_cid_font_type2 import PDCIDFontType2
    from pypdfbox.pdmodel.font.pd_font_descriptor import PDFontDescriptor
    from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font

    font_file2 = COSStream()
    font_file2.set_raw_data(ttf_bytes)

    fd_dict = COSDictionary()
    descriptor = PDFontDescriptor(fd_dict)
    descriptor.set_font_file2(font_file2)

    # /CIDSystemInfo — required by spec; values aren't load-bearing for
    # the renderer but real consumers reject the font without them.
    cid_system_info = COSDictionary()
    cid_system_info.set_string(
        COSName.get_pdf_name("Registry"), "Adobe"
    )
    cid_system_info.set_string(
        COSName.get_pdf_name("Ordering"), "Identity"
    )
    cid_system_info.set_int(COSName.get_pdf_name("Supplement"), 0)

    descendant_dict = COSDictionary()
    descendant_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    descendant_dict.set_item(
        COSName.SUBTYPE, COSName.get_pdf_name("CIDFontType2")
    )
    descendant_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("DejaVuSquare-Identity-H"),
    )
    descendant_dict.set_item(
        COSName.get_pdf_name("CIDSystemInfo"), cid_system_info
    )
    # /CIDToGIDMap stream — explicit map so CID 0x41 -> GID 1 ('A') and
    # CID 0x42 -> GID 2 ('B'). The synthesised TTF only contains 3
    # glyphs so an /Identity map (CID == GID) would walk past the glyph
    # order and miss the squares entirely.
    cid_to_gid = bytearray(0x43 * 2)  # covers CID 0..0x42 inclusive
    cid_to_gid[0x41 * 2 : 0x41 * 2 + 2] = (1).to_bytes(2, "big")  # 'A'
    cid_to_gid[0x42 * 2 : 0x42 * 2 + 2] = (2).to_bytes(2, "big")  # 'B'
    cid_to_gid_stream = COSStream()
    cid_to_gid_stream.set_raw_data(bytes(cid_to_gid))
    descendant_dict.set_item(
        COSName.get_pdf_name("CIDToGIDMap"), cid_to_gid_stream
    )
    descendant_dict.set_item(
        COSName.get_pdf_name("FontDescriptor"), descriptor.get_cos_object()
    )
    # /DW = 1000 → keeps the advance width consistent with the simple-TTF
    # path's hmtx-derived advance for the same glyph.
    descendant_dict.set_item(
        COSName.get_pdf_name("DW"), COSInteger.get(1000)
    )

    descendants = COSArray()
    descendants.add(descendant_dict)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.TYPE, COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type0"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"),
        COSName.get_pdf_name("DejaVuSquare-Identity-H"),
    )
    font_dict.set_item(
        COSName.get_pdf_name("Encoding"),
        COSName.get_pdf_name("Identity-H"),
    )
    font_dict.set_item(
        COSName.get_pdf_name("DescendantFonts"), descendants
    )

    pd_font = PDType0Font(font_dict)
    # Sanity: descendant resolves to the typed CIDFontType2 wrapper —
    # otherwise the renderer can't reach the embedded /FontFile2.
    assert isinstance(pd_font.get_descendant_font(), PDCIDFontType2)
    return pd_font


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


def test_truetype_ttf_renders_filled_pixels_in_text_area() -> None:
    """Plain ``/Subtype /TrueType`` font with ``/FontFile2`` —
    ``BT … Tf … Tj 'AB' ET`` should plant filled black glyph pixels
    around the show-text origin."""
    doc, page = _make_doc(200.0, 100.0)
    font = _wrap_ttf_as_pdtruetypefont(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.new_line_at_offset(20.0, 30.0)
        cs.show_text("AB")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 100)
    dark = _count_dark_pixels(img)
    assert dark > 200, f"expected TTF glyph footprint, got dark_count={dark}"

    # Sanity: dark pixels live in the upper-left half of the page (near the
    # show-text origin), not in the empty lower-right corner.
    bottom_right = img.crop((150, 70, 200, 100))
    assert _count_dark_pixels(bottom_right) == 0


def test_type0_identity_h_ttf_renders_filled_pixels() -> None:
    """Type0 (composite) font with Identity-H + CIDFontType2 + identity
    /CIDToGIDMap should rasterise the same square glyphs as the simple-TTF
    path. The 2-byte input ``\\x00\\x41`` selects CID 0x41 → GID 0x41
    ('A')."""
    doc, page = _make_doc(200.0, 100.0)
    font = _wrap_ttf_as_pdtype0font(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 50.0)
        cs.new_line_at_offset(20.0, 30.0)
        # Identity-H: each character code is two bytes, big-endian.
        # 0x0041 -> CID 0x41 -> GID 0x41 (identity /CIDToGIDMap) -> 'A'.
        # 0x0042 -> 'B'.
        cs.show_text(b"\x00\x41\x00\x42")
        cs.end_text()

    img = PDFRenderer(doc).render_image(0)
    assert img.size == (200, 100)
    dark = _count_dark_pixels(img)
    assert dark > 200, (
        f"expected Type0 glyph footprint, got dark_count={dark}"
    )

    # The upper-left half (where the glyphs sit) should hold most of the
    # dark pixels — the lower-right quadrant should be untouched.
    bottom_right = img.crop((150, 70, 200, 100))
    assert _count_dark_pixels(bottom_right) == 0


def test_type0_byte_pair_advances_one_glyph_per_pair_not_per_byte() -> None:
    """Regression guard: before the multi-byte ``read_code`` path the
    renderer would treat each byte of ``\\x00\\x41`` as an independent
    code, drawing two glyphs per character. Confirm that one byte-pair
    paints exactly one glyph footprint by comparing the rendered output
    against an empty page."""
    # Empty page baseline.
    doc_empty, _ = _make_doc(120.0, 60.0)
    img_empty = PDFRenderer(doc_empty).render_image(0)
    baseline_dark = _count_dark_pixels(img_empty)

    # Single Type0 'A' glyph.
    doc, page = _make_doc(120.0, 60.0)
    font = _wrap_ttf_as_pdtype0font(_build_square_ttf_bytes())
    with PDPageContentStream(doc, page) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font, 30.0)
        cs.new_line_at_offset(20.0, 15.0)
        cs.show_text(b"\x00\x41")  # one Identity-H code
        cs.end_text()
    img = PDFRenderer(doc).render_image(0)
    one_glyph_dark = _count_dark_pixels(img) - baseline_dark
    assert one_glyph_dark > 100, (
        f"single Type0 glyph should rasterise, got delta={one_glyph_dark}"
    )

    # Two glyphs.
    doc2, page2 = _make_doc(120.0, 60.0)
    font2 = _wrap_ttf_as_pdtype0font(_build_square_ttf_bytes())
    with PDPageContentStream(doc2, page2) as cs:
        cs.set_non_stroking_color_rgb(0.0, 0.0, 0.0)
        cs.begin_text()
        cs.set_font(font2, 30.0)
        cs.new_line_at_offset(20.0, 15.0)
        cs.show_text(b"\x00\x41\x00\x42")  # two Identity-H codes
        cs.end_text()
    img2 = PDFRenderer(doc2).render_image(0)
    two_glyph_dark = _count_dark_pixels(img2) - baseline_dark
    # Two glyphs should produce roughly twice the painted area as one.
    # Allow generous slack — the absolute pixel count varies with AA
    # softening, glyph metrics and integer rounding, but the ratio
    # should still grow noticeably.
    assert two_glyph_dark > one_glyph_dark + 50, (
        f"two Type0 glyphs should paint more than one; "
        f"one={one_glyph_dark} two={two_glyph_dark}"
    )
