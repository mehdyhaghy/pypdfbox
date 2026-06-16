from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text import PDFTextStripper, TextPosition


class StallingCMap:
    def read_code(self, _stream: Any) -> int:
        return 65

    def to_unicode(self, _code: int) -> str:
        return "unreachable"


class WidthFont(PDType1Font):
    def get_glyph_width(self, code: int) -> float:
        if code == 32:
            return 250.0
        return 0.0


def _make_page_with_stream(doc: PDDocument, content: bytes | None) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    if content is not None:
        stream = COSStream()
        stream.set_data(content)
        page.set_contents(stream)
    doc.add_page(page)
    return page


def test_wave488_configuration_accessors_round_trip() -> None:
    stripper = PDFTextStripper()
    bookmark = cast(Any, object())

    stripper.set_start_page("2")
    stripper.set_end_page("4")
    stripper.set_word_separator("|")
    stripper.set_line_separator("/")
    stripper.set_paragraph_start("<p>")
    stripper.set_paragraph_end("</p>")
    stripper.set_page_start("<page>")
    stripper.set_page_end("</page>")
    stripper.set_should_separate_by_beads(False)
    stripper.set_sort_by_position(True)
    stripper.set_drop_threshold("3.5")
    stripper.set_indent_threshold("1.25")
    stripper.set_spacing_tolerance("0.75")
    stripper.set_average_char_tolerance("0.45")
    stripper.set_add_more_formatting(True)
    stripper.set_lenient_stream_parsing(False)
    stripper.set_ignore_content_stream_space_glyphs(True)
    stripper.set_should_flip_axes(True)
    stripper.set_article_start("<article>")
    stripper.set_article_end("</article>")
    stripper.set_start_bookmark(bookmark)
    stripper.set_end_bookmark(bookmark)

    assert stripper.get_start_page() == 2
    assert stripper.get_end_page() == 4
    assert stripper.get_word_separator() == "|"
    assert stripper.get_line_separator() == "/"
    assert stripper.get_paragraph_start() == "<p>"
    assert stripper.get_paragraph_end() == "</p>"
    assert stripper.get_page_start() == "<page>"
    assert stripper.get_page_end() == "</page>"
    assert stripper.get_should_separate_by_beads() is False
    assert stripper.is_should_separate_by_beads() is False
    assert stripper.get_separate_by_beads() is False
    assert stripper.is_sort_by_position() is True
    assert stripper.get_sort_by_position() is True
    assert stripper.get_drop_threshold() == 3.5
    assert stripper.get_indent_threshold() == 1.25
    assert stripper.get_spacing_tolerance() == 0.75
    assert stripper.get_average_char_tolerance() == 0.45
    assert stripper.get_add_more_formatting() is True
    assert stripper.is_lenient_stream_parsing() is False
    assert stripper.get_ignore_content_stream_space_glyphs() is True
    assert stripper.is_should_flip_axes() is True
    assert stripper.get_should_flip_axes() is True
    assert stripper.get_article_start() == "<article>"
    assert stripper.get_article_end() == "</article>"
    assert stripper.get_start_bookmark() is bookmark
    assert stripper.get_end_bookmark() is bookmark


def test_wave488_process_page_without_contents_resets_walk_state() -> None:
    doc = PDDocument()
    page = _make_page_with_stream(doc, None)
    stripper = PDFTextStripper()

    try:
        assert stripper.get_text(doc) == "\n"
        assert stripper.process_page(page) == ""
        # A contentless page is still a single (empty) article slot in
        # upstream's ``writePage`` loop, so ``charactersByArticle`` holds one
        # empty list rather than nothing (wave 1542: ``process_page`` now
        # mirrors upstream's empty-article bracketing for glyph-free pages).
        assert stripper.get_characters_by_article() == [[]]
    finally:
        doc.close()


def test_wave488_td_operator_sets_leading_and_next_line_origin() -> None:
    doc = PDDocument()
    _make_page_with_stream(
        doc,
        b"BT /F0 12 Tf 100 700 Td (one) Tj 25 -18 TD (two) Tj T* (three) Tj ET",
    )

    stripper = PDFTextStripper()
    stripper.set_indent_threshold(100.0)
    try:
        assert stripper.get_text(doc) == "one\ntwo\nthree\n"

        positions = stripper.get_characters_by_article()[0]
        assert [(p.text, p.x, p.y) for p in positions] == [
            ("one", 100.0, 700.0),
            ("two", 125.0, 682.0),
            ("three", 125.0, 664.0),
        ]
    finally:
        doc.close()


def test_wave488_cmap_lookup_parses_stream_and_caches_negative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pypdfbox.fontbox.cmap import CMapParser

    to_unicode = COSStream()
    to_unicode.set_data(b"fake-cmap")
    font_dict = COSDictionary()
    font_dict.set_item(COSName.get_pdf_name("ToUnicode"), to_unicode)

    resources = PDResources()
    resources.put(COSName.get_pdf_name("Font"), COSName.get_pdf_name("F0"), font_dict)
    page = PDPage()
    page.set_resources(resources)

    parsed = object()
    calls: list[bytes] = []

    def parse(self: CMapParser, data: bytes) -> object:
        calls.append(data)
        return parsed

    monkeypatch.setattr(CMapParser, "parse", parse)
    stripper = PDFTextStripper()
    stripper._active_page = page  # noqa: SLF001

    assert stripper._get_cmap_for_font(None) is None  # noqa: SLF001
    assert stripper._get_cmap_for_font("F0") is parsed  # noqa: SLF001
    assert stripper._get_cmap_for_font("F0") is parsed  # noqa: SLF001
    assert stripper._get_cmap_for_font("Missing") is None  # noqa: SLF001
    assert calls == [b"fake-cmap"]


def test_wave488_get_font_for_wraps_dictionary_and_caches_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pypdfbox.pdmodel.font as font_module

    font_dict = COSDictionary()
    resources = PDResources()
    resources.put(COSName.get_pdf_name("Font"), COSName.get_pdf_name("F0"), font_dict)
    page = PDPage()
    page.set_resources(resources)

    typed = PDType1Font()
    calls: list[COSDictionary] = []

    # PDResources.get_font now wraps every entry via PDFontFactory.create_font
    # (passing the resource cache as the second arg, wave 1487); the stub must
    # accept it. The font is wrapped once and cached by the stripper.
    def create_font(raw: COSDictionary, resource_cache: object | None = None) -> PDType1Font:
        calls.append(raw)
        return typed

    monkeypatch.setattr(font_module.PDFontFactory, "create_font", create_font)
    stripper = PDFTextStripper()
    stripper._active_page = page  # noqa: SLF001

    assert stripper._get_font_for(None) is None  # noqa: SLF001
    assert stripper._get_font_for("F0") is typed  # noqa: SLF001
    assert stripper._get_font_for("F0") is typed  # noqa: SLF001
    assert stripper._get_font_for("Missing") is None  # noqa: SLF001
    assert calls == [font_dict]


def test_wave488_decode_text_via_cmap_skips_misses_and_stops_on_stall() -> None:
    class FakeCMap:
        def read_code(self, stream: Any) -> int:
            value = stream.read(1)
            return value[0] if value else 0

        def to_unicode(self, code: int) -> str | None:
            return {65: "A", 67: "C"}.get(code)

    assert PDFTextStripper._decode_text_via_cmap(b"ABC", cast(Any, FakeCMap())) == "AC"

    assert PDFTextStripper._decode_text_via_cmap(b"A", cast(Any, StallingCMap())) == ""


def test_wave488_width_helpers_and_sorting_paths() -> None:
    assert PDFTextStripper._compute_width_of_space(WidthFont(), 20.0, fallback=9.0) == 5.0

    class BadWidthFont(PDType1Font):
        def get_glyph_width(self, _code: int) -> float:
            raise RuntimeError("bad width")

    assert PDFTextStripper._compute_width_of_space(BadWidthFont(), 20.0, fallback=9.0) == 9.0
    assert PDFTextStripper._compute_width_of_space(object(), 20.0, fallback=9.0) == 9.0

    stripper = PDFTextStripper()
    stripper.set_sort_by_position(True)
    stripper.set_drop_threshold(100.0)
    stripper.set_indent_threshold(100.0)
    positions = [
        TextPosition(text="bottom", x=10.0, y=100.0, font_size=10.0, width=10.0),
        TextPosition(text="top", x=20.0, y=200.0, font_size=10.0, width=10.0),
    ]
    assert stripper._format_positions(positions) == "top\nbottom"  # noqa: SLF001

    stripper.set_should_flip_axes(True)
    positions = [
        TextPosition(text="right", x=20.0, y=10.0, font_size=10.0, width=10.0),
        TextPosition(text="left", x=10.0, y=10.0, font_size=10.0, width=10.0),
    ]
    assert stripper._format_positions(positions) == "left\nright"  # noqa: SLF001


def test_wave488_partition_by_beads_defensive_paths() -> None:
    stripper = PDFTextStripper()
    pos = TextPosition(text="x", x=1.0, y=1.0, font_size=1.0)

    assert stripper._partition_by_beads([pos]) == []  # noqa: SLF001

    stripper._active_page = cast(Any, SimpleNamespace(get_thread_beads=lambda: []))  # noqa: SLF001
    assert stripper._partition_by_beads([pos]) == []  # noqa: SLF001

    stripper._active_page = cast(  # noqa: SLF001
        Any,
        SimpleNamespace(
            get_thread_beads=lambda: [
                None,
                SimpleNamespace(
                    get_rectangle=lambda: (_ for _ in ()).throw(RuntimeError("bad"))
                ),
                SimpleNamespace(get_rectangle=lambda: None),
            ]
        ),
    )
    assert stripper._partition_by_beads([pos]) == []  # noqa: SLF001

    rect = PDRectangle(0.0, 0.0, 5.0, 5.0)
    stripper._active_page = cast(  # noqa: SLF001
        Any,
        SimpleNamespace(
            get_thread_beads=lambda: [
                None,
                SimpleNamespace(get_rectangle=lambda: rect),
            ]
        ),
    )
    assert stripper._partition_by_beads([pos]) == [[pos]]  # noqa: SLF001
