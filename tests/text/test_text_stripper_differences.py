"""Tests for the two PDFTextStripper enhancements:

1. ``/Differences`` (DictionaryEncoding) glyph→unicode lookup for simple
   fonts that lack a ``/ToUnicode`` CMap.
2. Font-width-driven word-gap heuristic — when the active font carries a
   ``/Widths`` array, the per-character advance comes from the actual
   average width rather than the legacy 0.5-em monospace estimate.

Pages are hand-crafted from COS structures + content streams so the
tests don't depend on the upstream PDF corpus.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text import PDFTextStripper, TextPosition

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _make_type1_font(
    base_encoding: str | None,
    differences: list[object],
    widths: list[int] | None = None,
    first_char: int = 0,
) -> COSDictionary:
    """Build a minimal Type1 font dictionary with a DictionaryEncoding.

    ``differences`` is the raw /Differences array — a mix of ``int``
    (next code) and ``str`` (glyph name) entries, matching the wire
    format. ``widths`` (when supplied) populates ``/Widths`` starting
    at ``first_char``.
    """
    encoding_dict = COSDictionary()
    encoding_dict.set_item(
        COSName.get_pdf_name("Type"), COSName.get_pdf_name("Encoding")
    )
    if base_encoding is not None:
        encoding_dict.set_item(
            COSName.get_pdf_name("BaseEncoding"),
            COSName.get_pdf_name(base_encoding),
        )
    diffs_array = COSArray()
    for entry in differences:
        if isinstance(entry, int):
            diffs_array.add(COSInteger.get(entry))
        elif isinstance(entry, str):
            diffs_array.add(COSName.get_pdf_name(entry))
    encoding_dict.set_item(COSName.get_pdf_name("Differences"), diffs_array)

    font_dict = COSDictionary()
    font_dict.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    font_dict.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type1"))
    font_dict.set_item(
        COSName.get_pdf_name("BaseFont"), COSName.get_pdf_name("Helvetica")
    )
    font_dict.set_item(COSName.get_pdf_name("Encoding"), encoding_dict)

    if widths is not None:
        widths_array = COSArray()
        for w in widths:
            widths_array.add(COSInteger.get(w))
        font_dict.set_item(COSName.get_pdf_name("Widths"), widths_array)
        font_dict.set_item(
            COSName.get_pdf_name("FirstChar"), COSInteger.get(first_char)
        )
        font_dict.set_item(
            COSName.get_pdf_name("LastChar"),
            COSInteger.get(first_char + len(widths) - 1),
        )

    return font_dict


def _attach_font(page: PDPage, name: str, font_dict: COSDictionary) -> None:
    resources = PDResources()
    resources.put(
        COSName.get_pdf_name("Font"),
        COSName.get_pdf_name(name),
        font_dict,
    )
    page.set_resources(resources)


class _CapturingTextStripper(PDFTextStripper):
    def __init__(self) -> None:
        super().__init__()
        self.positions: list[TextPosition] = []

    def _format_positions(self, positions: list[TextPosition]) -> str:
        self.positions = list(positions)
        return super()._format_positions(positions)


# ---------------------------------------------------------------------------
# (1) /Differences-based glyph→unicode lookup
# ---------------------------------------------------------------------------


def test_differences_encoding_decodes_via_glyph_list() -> None:
    """A Type1 font with no /ToUnicode but a /Differences entry mapping
    byte 0x41 to the glyph name "Aogonek" (U+0104) should decode the
    show-text byte ``A`` as ``"Ą"`` rather than the Latin-1 fallback
    ``"A"``."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (A) Tj ET"
    )
    # /Differences: starting at code 0x41, replace the StandardEncoding
    # glyph (originally "A") with "Aogonek". The Adobe Glyph List maps
    # "Aogonek" → U+0104.
    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[0x41, "Aogonek"],
    )
    _attach_font(page, "F0", font_dict)

    out = PDFTextStripper().get_text(doc)
    assert out == "Ą\n"


def test_differences_encoding_overrides_only_listed_codes() -> None:
    """The /Differences overlay only replaces the codes it explicitly
    names; other codes still resolve through the /BaseEncoding (here
    WinAnsi) and the AGL — so 'B' (0x42) keeps its standard mapping."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (AB) Tj ET"
    )
    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[0x41, "Aogonek"],
    )
    _attach_font(page, "F0", font_dict)

    out = PDFTextStripper().get_text(doc)
    # 0x41 → Aogonek (U+0104), 0x42 → "B" (unchanged from WinAnsi).
    assert out == "ĄB\n"


def test_differences_encoding_consecutive_glyph_names() -> None:
    """``/Differences`` lets multiple glyph names follow one integer; the
    code increments for each subsequent name. Verify the increment
    actually happens — bytes 0x80 and 0x81 should both decode."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (\x80\x81) Tj ET"
    )
    # /Differences [128 /Aogonek /Eogonek] — 0x80 → "Aogonek" (U+0104),
    # 0x81 → "Eogonek" (U+0118).
    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[0x80, "Aogonek", "Eogonek"],
    )
    _attach_font(page, "F0", font_dict)

    out = PDFTextStripper().get_text(doc)
    assert out == "ĄĘ\n"


def test_to_unicode_takes_precedence_over_differences() -> None:
    """When a font carries both ``/ToUnicode`` and ``/Differences``, the
    CMap wins — it's the more authoritative mapping per PDF 32000-1
    §9.10.2."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc, b"BT /F0 12 Tf 100 700 Td (A) Tj ET"
    )
    # /Differences would map A → Aogonek (U+0104), but /ToUnicode says
    # 0x41 → U+03B1 (alpha). The CMap result must win.
    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[0x41, "Aogonek"],
    )
    cmap_body = (
        b"/CIDInit /ProcSet findresource begin\n"
        b"12 dict begin\n"
        b"begincmap\n"
        b"1 begincodespacerange <00> <FF> endcodespacerange\n"
        b"1 beginbfchar <41> <03B1> endbfchar\n"
        b"endcmap\n"
    )
    to_unicode = COSStream()
    to_unicode.set_data(cmap_body)
    font_dict.set_item(COSName.get_pdf_name("ToUnicode"), to_unicode)
    _attach_font(page, "F0", font_dict)

    out = PDFTextStripper().get_text(doc)
    assert out == "α\n"


# ---------------------------------------------------------------------------
# (2) font-width-based word spacing
# ---------------------------------------------------------------------------


def test_narrow_font_keeps_close_runs_joined() -> None:
    """A *narrow* font (avg width 200/1000 em) means the previous run's
    right edge is close to its origin, so a small x jump still triggers
    a word break.

    Two Tj at x=100 and x=140, font_size=12, narrow font → per-char
    advance ≈ 200/1000*12 = 2.4 user units. With a 3-char word the
    right edge sits at 100 + 3*2.4 = 107.2; the gap to the next
    origin (140) is 32.8 units, well above the 12*1.5 = 18 threshold —
    so a space is emitted.
    """
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (foo) Tj 40 0 Td (bar) Tj ET",
    )
    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[],
        widths=[200] * 256,
        first_char=0,
    )
    _attach_font(page, "F0", font_dict)

    out = PDFTextStripper().get_text(doc)
    assert out == "foo bar\n"


def test_wide_font_suppresses_word_break_for_same_gap() -> None:
    """A *wide* font (avg width 1000/1000 em) consumes the whole
    inter-Tj distance with its glyphs, so the same physical x jump
    that produced a word break for the narrow font now leaves no gap.

    Two Tj at x=100 and x=140, font_size=12, wide font → per-char
    advance = 1000/1000*12 = 12 user units. With a 3-char word the
    right edge sits at 100 + 3*12 = 136; the gap to the next origin
    (140) is only 4 units — well below the 18 threshold — so the runs
    concatenate.
    """
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (foo) Tj 40 0 Td (bar) Tj ET",
    )
    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[],
        widths=[1000] * 256,
        first_char=0,
    )
    _attach_font(page, "F0", font_dict)

    out = PDFTextStripper().get_text(doc)
    # Same content stream as the narrow-font test, different /Widths →
    # different word-break decision. This is the load-bearing assertion
    # the upgrade is meant to enable.
    assert out == "foobar\n"


def test_widths_zero_falls_back_to_half_em_estimate() -> None:
    """When every entry in ``/Widths`` is zero (or the array is missing
    entirely), the stripper must keep working — falling back to the
    legacy 0.5-em-per-char estimate used before this enhancement."""
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (foo) Tj 200 0 Td (bar) Tj ET",
    )
    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[],
        widths=[0] * 256,
        first_char=0,
    )
    _attach_font(page, "F0", font_dict)

    # Behaviour matches the no-font case — the 200-unit jump comfortably
    # exceeds the 0.5-em-derived right edge plus 18-unit threshold.
    out = PDFTextStripper().get_text(doc)
    assert out == "foo bar\n"


def test_text_positions_carry_resolved_font_and_width_metadata() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 3 Tw 1 Tc 100 700 Td (Hi) Tj ET",
    )
    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[],
        widths=[600] * 256,
        first_char=0,
    )
    _attach_font(page, "F0", font_dict)

    stripper = _CapturingTextStripper()
    assert stripper.get_text(doc) == "Hi\n"
    assert len(stripper.positions) == 1
    pos = stripper.positions[0]
    assert pos.text == "Hi"
    assert pos.font_name == "F0"
    assert pos.font is not None
    assert pos.resolved_font_name == "Helvetica"
    assert pos.width == pytest.approx(14.4)
    assert pos.width_of_space == pytest.approx(7.2)
    assert pos.char_spacing == 1.0
    assert pos.word_spacing == 3.0


def test_mixed_font_spacing_uses_previous_position_width() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"BT /Fwide 12 Tf 100 700 Td (foo) Tj /Fnarrow 12 Tf 40 0 Td (bar) Tj ET",
    )
    resources = PDResources()
    resources.put(
        COSName.get_pdf_name("Font"),
        COSName.get_pdf_name("Fwide"),
        _make_type1_font(
            base_encoding="WinAnsiEncoding",
            differences=[],
            widths=[1000] * 256,
            first_char=0,
        ),
    )
    resources.put(
        COSName.get_pdf_name("Font"),
        COSName.get_pdf_name("Fnarrow"),
        _make_type1_font(
            base_encoding="WinAnsiEncoding",
            differences=[],
            widths=[200] * 256,
            first_char=0,
        ),
    )
    page.set_resources(resources)

    stripper = _CapturingTextStripper()
    assert stripper.get_text(doc) == "foobar\n"
    assert [pos.text for pos in stripper.positions] == ["foo", "bar"]
    assert [pos.font_name for pos in stripper.positions] == ["Fwide", "Fnarrow"]
    assert [pos.width for pos in stripper.positions] == pytest.approx([36.0, 7.2])


# ---------------------------------------------------------------------------
# PDSimpleFont.get_average_font_width unit
# ---------------------------------------------------------------------------


def test_get_average_font_width_skips_zero_entries() -> None:
    """``get_average_font_width`` should average only the non-zero
    entries — sparse fonts (where most slots are .notdef = width 0)
    would otherwise report a misleadingly small advance."""
    from pypdfbox.pdmodel.font import PDType1Font

    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[],
        widths=[0, 500, 0, 700, 0],
        first_char=0,
    )
    font = PDType1Font(font_dict)
    # (500 + 700) / 2 = 600
    assert font.get_average_font_width() == 600.0


def test_get_average_font_width_empty_widths() -> None:
    """No ``/Widths`` array on a Standard 14 font → falls back to AFM mean.

    The fixture base font is Helvetica, so AFM bundled metrics provide the
    average. Wave 22 expanded PDType1Font.get_average_font_width to consult
    AFM after /Widths returns nothing; this used to return 0.0.
    """
    from pypdfbox.pdmodel.font import PDType1Font

    font_dict = _make_type1_font(
        base_encoding="WinAnsiEncoding",
        differences=[],
    )
    font = PDType1Font(font_dict)
    assert font.get_average_font_width() > 0.0
