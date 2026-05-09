from __future__ import annotations

import io
from collections.abc import Callable

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text import PDFTextStripper, TextPosition


def _make_page_with_stream(doc: PDDocument, content: bytes) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)
    return page


def _attach_font_with_to_unicode(page: PDPage, font_name: str, cmap_body: bytes) -> None:
    to_unicode = COSStream()
    to_unicode.set_data(cmap_body)

    font = COSDictionary()
    font.set_item(COSName.get_pdf_name("Type"), COSName.get_pdf_name("Font"))
    font.set_item(COSName.get_pdf_name("Subtype"), COSName.get_pdf_name("Type0"))
    font.set_item(COSName.get_pdf_name("ToUnicode"), to_unicode)

    resources = PDResources()
    resources.put(COSName.get_pdf_name("Font"), COSName.get_pdf_name(font_name), font)
    page.set_resources(resources)


def test_to_unicode_stream_without_mapping_skips_unmapped_codes() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (plain) Tj ET",
    )
    _attach_font_with_to_unicode(page, "F0", b"not a valid cmap")

    assert PDFTextStripper().get_text(doc) == "\n"


def test_tc_and_tw_state_is_visible_on_text_positions() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 2.5 Tc 7.5 Tw 100 700 Td (spaced) Tj ET",
    )

    stripper = PDFTextStripper()
    assert stripper.get_text(doc) == "spaced\n"

    pos = stripper.get_characters_by_article()[0][0]
    assert pos.text == "spaced"
    assert pos.char_spacing == 2.5
    assert pos.word_spacing == 7.5


def test_td_updates_line_origin_for_t_star_after_multiple_moves() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        (
            b"BT /F0 12 Tf 10 TL "
            b"100 700 Td (one) Tj "
            b"50 0 Td (two) Tj "
            b"T* (three) Tj "
            b"ET"
        ),
    )

    stripper = PDFTextStripper()
    assert stripper.get_text(doc) == "one two\nthree\n"

    positions = stripper.get_characters_by_article()[0]
    assert [p.text for p in positions] == ["one", "two", "three"]
    assert positions[2].x == 150.0
    assert positions[2].y == 690.0


def test_write_text_restores_output_and_current_page_when_page_hook_raises() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (boom) Tj ET")
    events: list[str] = []

    class FailingStripper(PDFTextStripper):
        def process_page(self, page: PDPage) -> str:
            events.append(f"process:{self.get_current_page_no()}")
            raise RuntimeError("page failed")

        def end_document(self, document: PDDocument) -> None:
            events.append(f"end:{self.get_current_page_no()}")

    stripper = FailingStripper()
    writer = io.StringIO()

    with pytest.raises(RuntimeError, match="page failed"):
        stripper.write_text(doc, writer)

    assert events == ["process:1", "end:1"]
    assert stripper.get_current_page_no() == 0
    assert stripper.get_output() is None
    assert writer.getvalue() == ""


def test_write_text_restores_previous_output_after_nested_call() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (outer) Tj ET")
    inner_doc = PDDocument()
    _make_page_with_stream(inner_doc, b"BT /F0 12 Tf 100 700 Td (inner) Tj ET")

    seen: list[object | None] = []

    class NestedStripper(PDFTextStripper):
        def write_string(
            self,
            text: str,
            text_positions: list[TextPosition],
            sink: Callable[[str], None],
        ) -> None:
            seen.append(self.get_output())
            if text == "outer":
                inner_writer = io.StringIO()
                self.write_text(inner_doc, inner_writer)
                assert inner_writer.getvalue() == "inner\n"
                seen.append(self.get_output())
            sink(text)

    writer = io.StringIO()
    stripper = NestedStripper()
    stripper.write_text(doc, writer)

    assert writer.getvalue() == "outer\n"
    assert seen[0] is writer
    assert seen[1] is not writer
    assert seen[2] is writer
    assert stripper.get_output() is None


def test_custom_write_string_can_suppress_text_but_still_process_positions() -> None:
    doc = PDDocument()
    _make_page_with_stream(doc, b"BT /F0 12 Tf 100 700 Td (visible) Tj ET")
    processed: list[str] = []

    class SuppressingStripper(PDFTextStripper):
        def process_text_position(self, text: TextPosition) -> None:
            processed.append(text.text)

        def write_string(
            self,
            text: str,
            text_positions: list[TextPosition],
            sink: Callable[[str], None],
        ) -> None:
            super().write_string(text, text_positions, lambda _piece: None)

    assert SuppressingStripper().get_text(doc) == "\n"
    assert processed == ["visible"]
