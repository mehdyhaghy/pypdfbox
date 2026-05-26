from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSStream, COSString
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition
from pypdfbox.text.pdf_text_stripper import _six_numbers, _two_numbers
from pypdfbox.util.matrix import Matrix


def _make_page_with_stream(doc: PDDocument, content: bytes | None) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    if content is not None:
        stream = COSStream()
        stream.set_data(content)
        page.set_contents(stream)
    doc.add_page(page)
    return page


def test_wave550_successful_walk_hooks_see_current_page_and_restore_cursor() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (one) Tj ET")
    second = _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (two) Tj ET")
    second_cos = second.get_cos_object()
    events: list[str] = []

    class HookStripper(PDFTextStripper):
        def start_document(self, document: PDDocument) -> None:
            assert document is doc
            events.append(f"start-doc:{self.get_current_page_no()}")

        def start_page(self, page: PDPage) -> None:
            events.append(
                f"start-page:{self.get_current_page_no()}:{page.get_cos_object() is second_cos}"
            )

        def end_page(self, page: PDPage) -> None:
            events.append(
                f"end-page:{self.get_current_page_no()}:{page.get_cos_object() is second_cos}"
            )

        def end_document(self, document: PDDocument) -> None:
            assert document is doc
            events.append(f"end-doc:{self.get_current_page_no()}")

    stripper = HookStripper()
    stripper.set_start_page(2)
    stripper.set_end_page(99)

    try:
        assert stripper.get_text(doc) == "two\n"
        assert events == [
            "start-doc:0",
            "start-page:2:True",
            "end-page:2:True",
            "end-doc:2",
        ]
        assert stripper.get_current_page_no() == 0
    finally:
        doc.close()


def test_wave550_empty_or_inverted_page_ranges_return_without_page_hooks() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (one) Tj ET")
    events: list[str] = []

    class HookStripper(PDFTextStripper):
        def start_document(self, document: PDDocument) -> None:
            events.append("start-doc")

        def start_page(self, page: PDPage) -> None:
            events.append("start-page")

        def end_document(self, document: PDDocument) -> None:
            events.append("end-doc")

    stripper = HookStripper()
    stripper.set_start_page(3)
    stripper.set_end_page(1)

    try:
        assert stripper.get_text(doc) == ""
        assert events == []
        assert stripper.get_current_page_no() == 0
    finally:
        doc.close()


def test_wave550_dispatch_handles_text_matrix_and_spacing_operands() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 10 Tf "
            b"1 0 0 1 50 600 Tm (first) Tj "
            b"4 Tc 8 Tw "
            b"50 0 Td (second) Tj "
            b"ET"
        ),
    )

    stripper = PDFTextStripper()
    try:
        assert stripper.get_text(doc) == "first second\n"
        first, second = stripper.get_characters_by_article()[0]
        assert first.text_matrix == [1.0, 0.0, 0.0, 1.0, 50.0, 600.0]
        assert second.x == 100.0
        assert second.char_spacing == 4.0
        assert second.word_spacing == 8.0
    finally:
        doc.close()


def test_wave550_helper_number_parsers_reject_short_or_nonnumeric_inputs() -> None:
    assert _two_numbers([]) == (0.0, 0.0)
    assert _two_numbers([COSInteger.get(1), COSName.get_pdf_name("bad")]) == (0.0, 0.0)
    assert _two_numbers([COSInteger.get(2), COSFloat("3.5")]) == (2.0, 3.5)

    valid = [
        COSInteger.get(1),
        COSInteger.get(2),
        COSInteger.get(3),
        COSInteger.get(4),
        COSInteger.get(5),
        COSInteger.get(6),
    ]
    assert _six_numbers(valid) == (1.0, 2.0, 3.0, 4.0, 5.0, 6.0)
    assert _six_numbers(valid[:5]) is None
    for index in range(6):
        operands = list(valid)
        operands[index] = COSName.get_pdf_name("bad")
        assert _six_numbers(operands) is None


def test_wave550_tj_array_ignores_non_text_and_non_number_entries() -> None:
    stripper = PDFTextStripper()
    state = type("State", (), {})()
    state.text_x = 10.0
    state.text_y = 20.0
    state.font_size = 10.0
    state.font_name = "F0"
    state.char_spacing = 0.0
    state.word_spacing = 0.0
    state.tm_a = 1.0
    state.tm_b = 0.0
    state.tm_c = 0.0
    state.tm_d = 1.0
    # The emitter composes the text matrix with the CTM; an identity CTM
    # leaves device-space positions equal to the text-space cursor.
    state.ctm = Matrix()
    positions: list[TextPosition] = []

    stripper._emit_tj_array(  # noqa: SLF001
        COSArray(
            [
                COSString(b"A"),
                COSName.get_pdf_name("ignored"),
                COSInteger.get(-1000),
                COSString(b"B"),
            ]
        ),
        state,
        positions,
    )

    assert [p.text for p in positions] == ["A", "B"]
    assert positions[1].x == 25.0


def test_wave550_paragraph_indent_helpers_honor_space_width_fallback_and_flip_axes() -> None:
    stripper = PDFTextStripper()
    prev = TextPosition(text="a", x=10.0, y=50.0, font_size=12.0, width_of_space=0.0)
    indented = TextPosition(text="b", x=17.0, y=42.0, font_size=12.0)
    same_indent = TextPosition(text="c", x=14.0, y=42.0, font_size=12.0)

    assert stripper.is_para_break_indented(indented, prev) is True
    assert stripper.start_of_paragraph(indented, prev) is True
    assert stripper.is_para_break_indented(same_indent, prev) is False

    stripper.set_should_flip_axes(True)
    flipped = TextPosition(text="d", x=18.0, y=57.0, font_size=12.0, width_of_space=0.0)
    assert stripper.is_para_break_indented(flipped, prev) is True


def test_wave550_direct_noop_hooks_are_callable() -> None:
    stripper = PDFTextStripper()
    position = TextPosition(text="x", x=0.0, y=0.0, font_size=1.0)

    assert stripper.process_text_position(position) is None
    assert stripper.write_characters(position) is None
    assert stripper.start_article() is None
    assert stripper.start_article(False) is None
    assert stripper.end_article() is None
