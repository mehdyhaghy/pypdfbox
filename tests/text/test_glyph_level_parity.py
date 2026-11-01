"""Glyph-level text extraction parity with PDFBox 3.0.8.

``PDFTextStripper`` emits one ``TextPosition`` per glyph and lays them out
with upstream's ``writePage`` logic on upstream's ``TextPosition``
geometry (``getX`` / ``getY`` / ``getWidth`` and their ``DirAdj``
variants, in float). These tests pin the cases that used to differ from
``ExtractText``: composite fonts without ``/ToUnicode`` (predefined UCS2
CMaps), text rotated within the page, glyph-wise sorting, the Helvetica
fallback for a missing font, graphics-state text parameters, paragraph and
article markers, and the space width taken from the font.

The expected strings are PDFBox 3.0.8 output; the live differentials are
in ``test_glyph_level_parity_live.py``.

Hand-written (not ported from upstream JUnit).
"""

from pathlib import Path

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.interactive.pagenavigation import PDThreadBead
from pypdfbox.text import PDFTextStripper, TextPosition
from pypdfbox.text._tim_sort import ComparisonContractError, tim_sort
from pypdfbox.text.pdf_text_stripper import _java_compare
from pypdfbox.util.iterative_merge_sort import IterativeMergeSort

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _strip(path: Path, *, sort: bool = False, **options: bool) -> str:
    doc = PDDocument.load(str(path))
    try:
        stripper = PDFTextStripper()
        stripper.set_sort_by_position(sort)
        if "suppress" in options:
            stripper.set_suppress_duplicate_overlapping_text(options["suppress"])
        if "ignore_spaces" in options:
            stripper.set_ignore_content_stream_space_glyphs(options["ignore_spaces"])
        if "add_more" in options:
            stripper.set_add_more_formatting(options["add_more"])
        if options.get("markers"):
            stripper.set_article_start("<A>")
            stripper.set_article_end("</A>")
            stripper.set_paragraph_start("<P>")
            stripper.set_paragraph_end("</P>")
            stripper.set_page_start("<PG>")
            stripper.set_page_end("</PG>")
        return stripper.get_text(doc)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# fixtures: PDFBox 3.0.8 ExtractText output
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("sort", [False, True], ids=["default", "sort"])
def test_cns1_composite_font_without_to_unicode(sort: bool) -> None:
    # /UniCNS-UCS2-H encoding, no /ToUnicode: the Unicode comes from the
    # predefined Adobe-CNS1-UCS2 CMap, not from the raw code bytes.
    pdf = _FIXTURES / "pdmodel" / "font" / "PDFBOX-6249-cns1-nonembedded-latin.pdf"
    assert _strip(pdf, sort=sort) == "Hello Tika 123 中文\n"


def test_rotated_text_directions() -> None:
    pdf = _FIXTURES / "text" / "rotated_text_dir.pdf"
    # Unsorted, lines are grouped on the page axes, so vertical text breaks
    # wherever successive glyphs stop overlapping vertically.
    assert _strip(pdf) == "Zero\nN\nin\net\ny\nOneEighty\nT\nw\noS\neventy\n"
    # Sorted, the direction-adjusted coordinates keep each word together.
    assert _strip(pdf, sort=True) == "Zero\nNinety\nOneEighty\nTwoSeventy\n"


def test_overlay_of_rotated_pages() -> None:
    pdf = _FIXTURES / "multipdf" / "PDFBOX-6049-ExpectedResult.pdf"
    block = (
        "rotation 0\nO\nve\nrla\ny\nro\ntatio\nn\n 90O\nve\nrla\ny\n"
        "rotation 180\nO\nve\nrla\ny\nro\nta\nti\no\nn\n 2\n70\nO\nve\nrla\ny\n"
    )
    assert _strip(pdf) == block * 2
    sorted_block = (
        "rotation 0\nOverlay\nrotation 90Overlay\nrotation 180\nOverlay\n"
        "Orvotation 270\nerlay\n"
    )
    assert _strip(pdf, sort=True) == sorted_block * 2


def test_upside_down_text_on_upside_down_page() -> None:
    # Tm -1 0 0 -1 on /Rotate 180: upstream takes the absolute glyph height
    # and space width, so the letters are not spaced apart.
    pdf = _FIXTURES / "multipdf" / "rot180.pdf"
    assert _strip(pdf) == "Page rotation: 180\n"
    assert _strip(pdf, sort=True) == "Page rotation: 180\n"


def test_sorting_interleaves_overlapping_glyphs() -> None:
    # Sorting works glyph by glyph: an overlay drawn across a line of text
    # is merged into it character by character, as in PDFBox.
    pdf = _FIXTURES / "multipdf" / "Overlayed-with-rot0.pdf"
    line = (
        "A quick movement of the enemy will jeopardPizaeg seix r goutnabtiooants:."
        "  0Heavy boxes perform quick waltzes and jigs."
    )
    assert line in _strip(pdf, sort=True).splitlines()


# ---------------------------------------------------------------------------
# synthetic content streams
# ---------------------------------------------------------------------------


def _font_dict(base_font: str) -> COSDictionary:
    font = COSDictionary()
    font.set_item(COSName.TYPE, COSName.FONT)
    font.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type1"))
    font.set_item(COSName.BASE_FONT, COSName.get_pdf_name(base_font))
    font.set_item(COSName.get_pdf_name("Encoding"), COSName.get_pdf_name("WinAnsiEncoding"))
    return font


def _build(
    path: Path,
    contents: list[bytes],
    *,
    beads: list[tuple[float, float, float, float]] | None = None,
    form: bytes | None = None,
) -> Path:
    doc = PDDocument()
    try:
        for content in contents:
            page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
            stream = COSStream()
            stream.set_data(content)
            page.set_contents(stream)
            fonts = COSDictionary()
            fonts.set_item(COSName.get_pdf_name("F1"), _font_dict("Helvetica"))
            fonts.set_item(COSName.get_pdf_name("F2"), _font_dict("Courier"))
            resources = COSDictionary()
            resources.set_item(COSName.FONT, fonts)
            if form is not None:
                xobject = COSStream()
                xobject.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Form"))
                xobject.set_item(
                    COSName.get_pdf_name("BBox"),
                    COSArray([COSFloat(0.0), COSFloat(0.0), COSFloat(612.0), COSFloat(792.0)]),
                )
                xobject.set_data(form)
                xobjects = COSDictionary()
                xobjects.set_item(COSName.get_pdf_name("Fm1"), xobject)
                resources.set_item(COSName.get_pdf_name("XObject"), xobjects)
            page.get_cos_object().set_item(COSName.RESOURCES, resources)
            if beads:
                bead_objects = []
                for rect in beads:
                    bead = PDThreadBead()
                    bead.set_rectangle(PDRectangle(*rect))
                    bead_objects.append(bead)
                page.set_thread_beads(bead_objects)
            doc.add_page(page)
        doc.save(str(path))
    finally:
        doc.close()
    return path


def test_one_position_per_glyph_and_one_write_string_per_word(tmp_path: Path) -> None:
    # Two strings apart: the gap is a word break (a space glyph would
    # instead be part of the word).
    pdf = _build(tmp_path / "w.pdf", [b"BT /F1 12 Tf 100 700 Td (foo) Tj 20 0 Td (bar) Tj ET"])
    glyphs: list[str] = []
    words: list[list[str]] = []

    class Recorder(PDFTextStripper):
        def process_text_position(self, text: TextPosition) -> None:
            glyphs.append(text.get_unicode())

        def write_string(self, text, text_positions, sink) -> None:  # type: ignore[override]
            words.append([p.get_unicode() for p in text_positions])
            super().write_string(text, text_positions, sink)

    doc = PDDocument.load(str(pdf))
    try:
        assert Recorder().get_text(doc) == "foo bar\n"
    finally:
        doc.close()
    assert glyphs == list("foobar")
    assert words == [["f", "o", "o"], ["b", "a", "r"]]


def test_missing_font_falls_back_to_helvetica(tmp_path: Path) -> None:
    # /F9 is not in the resources: upstream shows the text in Helvetica, so
    # the glyph advances are Helvetica's (A = 667, B = 667 thousandths).
    pdf = _build(tmp_path / "f.pdf", [b"BT /F9 10 Tf 100 700 Td (AB) Tj ET"])
    doc = PDDocument.load(str(pdf))
    try:
        stripper = PDFTextStripper()
        assert stripper.get_text(doc) == "AB\n"
        first, second = stripper.get_characters_by_article()[0]
    finally:
        doc.close()
    assert first.get_font().get_name() == "Helvetica"
    assert second.x == pytest.approx(106.67, abs=1e-4)


def test_q_restores_text_state(tmp_path: Path) -> None:
    # The font, size and character spacing belong to the graphics state:
    # after Q the 12pt Helvetica without spacing is back (PDFBox 3.0.8 gives
    # the same text; 3pt spacing stays under 20pt Courier's word gap).
    pdf = _build(
        tmp_path / "q.pdf",
        [
            b"BT /F1 12 Tf ET q BT /F2 20 Tf 3 Tc 100 600 Td (inner) Tj ET Q "
            b"BT 100 700 Td (outer) Tj ET"
        ],
    )
    doc = PDDocument.load(str(pdf))
    try:
        stripper = PDFTextStripper()
        text = stripper.get_text(doc)
        glyphs = stripper.get_characters_by_article()[0]
    finally:
        doc.close()
    assert text == "inner\nouter\n"
    outer = glyphs[5]
    assert outer.get_unicode() == "o"
    assert outer.get_font().get_name() == "Helvetica"
    assert outer.tf_font_size == 12.0


def test_form_xobject_inherits_font(tmp_path: Path) -> None:
    # The form has no Tf: it draws with the caller's current font.
    pdf = _build(
        tmp_path / "x.pdf",
        [b"BT /F2 10 Tf ET q /Fm1 Do Q"],
        form=b"BT 100 700 Td (in form) Tj ET",
    )
    doc = PDDocument.load(str(pdf))
    try:
        stripper = PDFTextStripper()
        assert stripper.get_text(doc) == "in form\n"
        glyph = stripper.get_characters_by_article()[0][0]
    finally:
        doc.close()
    assert glyph.get_font().get_name() == "Courier"


def test_actual_text_tail_glyphs_do_not_form_a_word(tmp_path: Path) -> None:
    # Every glyph of the span after the first carries "" as its unicode; a
    # trailing run of them is not a word, so no separator is written.
    pdf = _build(
        tmp_path / "a.pdf",
        [
            b"/Span <</ActualText (Hello)>> BDC BT /F1 18 Tf 6 Tc "
            b"0 1 -1 0 300 500 Tm (  ) Tj ET EMC"
        ],
    )
    assert _strip(pdf, sort=True) == "Hello\n"


def test_empty_article_slots_are_wrapped_and_persist(tmp_path: Path) -> None:
    # Page 1 has two beads (5 article slots); page 2 has none but reuses
    # the 5 slots, and its glyphs land in the last one. The " Right<P></P>"
    # is upstream's ``inParagraph`` bookkeeping across articles (the text
    # is PDFBox 3.0.8 output).
    pdf = _build(
        tmp_path / "b.pdf",
        [
            b"BT /F1 12 Tf 72 700 Td (Left) Tj 300 0 Td (Right) Tj ET",
            b"BT /F1 12 Tf 72 700 Td (Next) Tj ET",
        ],
        beads=[(60.0, 600.0, 200.0, 760.0), (340.0, 600.0, 500.0, 760.0)],
    )
    doc = PDDocument.load(str(pdf))
    try:
        # Only page 1 carries beads; drop them from page 2.
        doc.get_page(1).get_cos_object().remove_item(COSName.get_pdf_name("B"))
        doc.save(str(tmp_path / "b2.pdf"))
    finally:
        doc.close()
    text = _strip(tmp_path / "b2.pdf", markers=True)
    assert text == (
        "<PG><A></A><A><P>Left</P></A><A></A><A> Right<P></P></A><A></A></PG>"
        "<PG><A></A><A></A><A></A><A></A><A><P>Next</P></A></PG>"
    )


def test_paragraph_end_without_start_opens_one() -> None:
    chunks: list[str] = []
    stripper = PDFTextStripper()
    stripper.set_paragraph_start("<P>")
    stripper.set_paragraph_end("</P>")
    stripper.write_paragraph_end(chunks.append)
    stripper.write_paragraph_start(chunks.append)
    stripper.write_paragraph_start(chunks.append)
    assert chunks == ["<P>", "</P>", "<P>", "</P>", "<P>"]


def test_ignored_space_glyphs_stay_in_the_article(tmp_path: Path) -> None:
    pdf = _build(tmp_path / "s.pdf", [b"BT /F1 12 Tf 100 700 Td (A B) Tj ET"])
    doc = PDDocument.load(str(pdf))
    try:
        stripper = PDFTextStripper()
        stripper.set_ignore_content_stream_space_glyphs(True)
        # The gap the space leaves still reads as a word break.
        assert stripper.get_text(doc) == "A B\n"
        assert [p.get_unicode() for p in stripper.get_characters_by_article()[0]] == [
            "A",
            " ",
            "B",
        ]
    finally:
        doc.close()


def test_glyph_geometry_matches_upstream_getters(tmp_path: Path) -> None:
    # A glyph rotated by 90 degrees on an unrotated page: upstream's
    # getWidth() is the x extent of its advance (zero), getWidthDirAdj()
    # the advance itself.
    pdf = _build(tmp_path / "g.pdf", [b"BT /F1 10 Tf 0 1 -1 0 300 400 Tm (A) Tj ET"])
    doc = PDDocument.load(str(pdf))
    try:
        stripper = PDFTextStripper()
        stripper.get_text(doc)
        glyph = stripper.get_characters_by_article()[0][0]
    finally:
        doc.close()
    assert glyph.get_dir() == 90.0
    assert glyph.width == pytest.approx(0.0, abs=1e-5)
    assert glyph.device_end_y - glyph.device_y == pytest.approx(6.67, abs=1e-4)


# ---------------------------------------------------------------------------
# Java List.sort and IterativeMergeSort
# ---------------------------------------------------------------------------


def _rock_paper_scissors(a: int, b: int) -> int:
    # Antisymmetric but not transitive: 0 < 1 < 2 < 0.
    if a == b:
        return 0
    return -1 if (b - a) % 3 == 1 else 1


def test_tim_sort_matches_list_sort_for_a_consistent_comparator() -> None:
    values = [(i * 7919) % 101 for i in range(300)]
    expected = sorted(values)
    tim_sort(values, lambda a, b: (a > b) - (a < b))
    assert values == expected


def test_tim_sort_is_stable() -> None:
    values = [(i % 5, i) for i in range(200)]
    tim_sort(values, lambda a, b: (a[0] > b[0]) - (a[0] < b[0]))
    assert values == sorted(values, key=lambda v: v[0])


# Java's TimSort rejects this sequence ("Comparison method violates its
# general contract!"), checked against Java 25.
_INCONSISTENT = [
    0, 0, 1, 2, 1, 0, 1, 0, 1, 0, 0, 2, 2, 2, 2, 0, 1, 0, 2, 2, 1, 2, 2, 0, 0, 1,
    2, 2, 2, 1, 2, 1, 0, 2, 0, 1, 1, 0, 2, 2, 1, 1, 1, 2, 0, 1, 2, 1, 0, 1, 2, 2,
    0, 1, 0, 1, 0, 1, 2, 2, 0, 2, 0, 2,
]  # fmt: skip


def test_tim_sort_reports_an_inconsistent_comparator() -> None:
    values = list(_INCONSISTENT)
    with pytest.raises(ComparisonContractError):
        tim_sort(values, _rock_paper_scissors)
    # Like Java's array, the list is left as a permutation of the input.
    assert sorted(values) == sorted(_INCONSISTENT)


def test_iterative_merge_sort_follows_upstream_comparisons() -> None:
    # Bottom-up merge taking from the right block only when it is strictly
    # smaller: with the non-transitive comparator the order is fully
    # determined by that sequence of comparisons (PDFBox 3.0.8 result).
    values = [2, 1, 0, 2, 0, 1, 1, 2]
    IterativeMergeSort.sort(values, _rock_paper_scissors)
    assert values == [0, 1, 1, 1, 2, 2, 2, 0]


def test_comparator_is_upstream_text_position_comparator() -> None:
    def glyph(x: float, y: float) -> TextPosition:
        pos = TextPosition(text="x", x=x, y=y, font_size=10.0, height=7.0)
        pos.page_width = 612.0
        pos.page_height = 792.0
        return pos

    upper = glyph(100.0, 700.0)
    lower = glyph(50.0, 600.0)
    same_line_right = glyph(200.0, 703.0)
    # Higher on the page sorts first; overlapping lines compare by x.
    assert _java_compare(upper, lower) == -1
    assert _java_compare(upper, same_line_right) == -1
    assert _java_compare(same_line_right, upper) == 1


# ---------------------------------------------------------------------------
# PDFont.get_space_width follows upstream's order
# ---------------------------------------------------------------------------


class _SpaceFont(PDFont):
    def __init__(self, mapping: int | None, string_width: float, program: float) -> None:
        super().__init__()
        self._mapping = mapping
        self._string_width = string_width
        self._program = program

    def has_to_unicode(self) -> bool:
        return self._mapping is not None

    def get_to_unicode_cmap(self):  # type: ignore[no-untyped-def]
        mapping = self._mapping

        class _CMap:
            def get_space_mapping(self) -> int:
                return mapping  # type: ignore[return-value]

        return _CMap() if mapping is not None else None

    def get_string_width(self, text: str) -> float:
        return self._string_width

    def get_width(self, code: int) -> float:
        return 0.0

    def get_width_from_font(self, code: int) -> float:
        return self._program

    def get_average_font_width(self) -> float:
        return 459.0


def test_space_width_with_to_unicode_skips_string_width() -> None:
    # PDFBOX eu-001 Symbol font: a ToUnicode CMap without a space mapping,
    # so upstream asks the font program (548.8281), not getStringWidth.
    assert _SpaceFont(-1, 1000.0, 548.8281).get_space_width() == 548.8281
    assert _SpaceFont(-1, 1000.0, 0.0).get_space_width() == 459.0
    assert _SpaceFont(None, 1000.0, 548.8281).get_space_width() == 1000.0
