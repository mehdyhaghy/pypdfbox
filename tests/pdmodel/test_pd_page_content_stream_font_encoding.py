"""``show_text`` and friends encode through the current font.

Regression tests for the content-stream writers: ``str`` text must go
through ``font.encode`` (with subset tracking) and be written with
``COSWriter.write_string``, as upstream
``PDAbstractContentStream.showTextInternal`` does. Before the fix the
writers encoded ``str`` as Latin-1 / UTF-16BE regardless of the font, so a
Type 0 (Identity-H) font showed the wrong glyphs and text extraction of the
saved file returned garbage.
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.font.encoding.win_ansi_encoding import WinAnsiEncoding
from pypdfbox.pdmodel.font.pd_true_type_font import PDTrueTypeFont
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.font.pd_type1_font import PDType1Font
from pypdfbox.pdmodel.graphics.form import PDFormXObject
from pypdfbox.pdmodel.graphics.pattern.pd_tiling_pattern import PDTilingPattern
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_content_stream import (
    PDAppearanceContentStream,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.pd_abstract_content_stream import PDAbstractContentStream
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_form_content_stream import PDFormContentStream
from pypdfbox.pdmodel.pd_page import PDPage
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream
from pypdfbox.pdmodel.pd_pattern_content_stream import PDPatternContentStream
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.text.pdf_text_stripper import PDFTextStripper

_TTF = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _page_doc() -> tuple[PDDocument, PDPage]:
    doc = PDDocument()
    page = PDPage()
    doc.add_page(page)
    return doc, page


def _save_reload(doc: PDDocument) -> PDDocument:
    buf = io.BytesIO()
    doc.save(buf)
    return PDDocument.load(buf.getvalue())


# ------------------------------------------------------------------
# Type 0 (Identity-H) fonts
# ------------------------------------------------------------------


def test_type0_show_text_writes_font_encoded_bytes() -> None:
    doc, page = _page_doc()
    font = PDType0Font.load(doc, str(_TTF))
    assert font.encode("AB") == b"\x00$\x00%"
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text("AB")
        cs.end_text()
    # Literal form: the 2-byte codes are 7-bit and carry no CR/LF.
    assert page.get_contents() == b"BT\n/F1 12 Tf\n(\x00$\x00%) Tj\nET\n"
    doc.close()


def test_type0_text_operators_all_encode_through_font() -> None:
    doc, page = _page_doc()
    font = PDType0Font.load(doc, str(_TTF))
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.set_leading(14)
        cs.move_to_next_line_show_text("A")
        cs.set_spacings_show_text(1, 2, "B")
        cs.show_text_with_positioning(["A", -100, "B"])
        cs.end_text()
    body = page.get_contents()
    assert b"(\x00$) '\n" in body
    assert b'1 2 (\x00%) "\n' in body
    assert b"[(\x00$)-100 (\x00%)] TJ\n" in body
    doc.close()


def test_type0_glyph_ids_needing_escape_or_hex() -> None:
    # LiberationSans glyph ids: 'E' = 0x28, 'F' = 0x29, 'y' = 0x5C (escaped
    # in literal form); "'" = 0x0A and '*' = 0x0D force hex form.
    doc, page = _page_doc()
    font = PDType0Font.load(doc, str(_TTF))
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text("EFy")
        cs.show_text("'*")
        cs.end_text()
    body = page.get_contents()
    assert b"(\x00\\(\x00\\)\x00\\\\) Tj\n" in body
    assert b"<000A000D> Tj\n" in body
    doc.close()


def test_type0_subset_round_trip_keeps_glyphs_and_extracts_text() -> None:
    doc, page = _page_doc()
    font = PDType0Font.load(doc, str(_TTF))
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.new_line_at_offset(72, 700)
        cs.show_text("Hello World")
        cs.show_text_with_positioning([" Hi", -50.0, "there"])
        cs.end_text()
    shown = "Hello World Hithere"
    codes = {ch: int.from_bytes(font.encode(ch), "big") for ch in shown}
    # set_font queued the subset font; save() drains the queue.
    assert font in doc.get_fonts_to_subset()
    with _save_reload(doc) as reloaded:
        assert doc.get_fonts_to_subset() == set()
        text = PDFTextStripper().get_text(reloaded)
        assert text == "Hello World Hithere\n"
        res = reloaded.get_page(0).get_resources()
        names = list(res.get_font_names())
        loaded = res.get_font(names[0])
        base = loaded.get_name()
        assert base[6] == "+" and base[:6].isupper()
        assert base.endswith("LiberationSans")
        descendant = loaded.get_descendant_font()
        ttf = descendant.get_true_type_font()
        # Far fewer glyphs than the ~2,600 in the full program.
        assert ttf.get_number_of_glyphs() < 100
        # Every shown code resolves to a real glyph with a real width.
        for ch, code in codes.items():
            if ch != " ":
                assert descendant.code_to_gid(code) > 0
            assert loaded.get_width(code) > 0
    doc.close()


def test_type0_without_subset_is_not_queued() -> None:
    doc, page = _page_doc()
    font = PDType0Font.load(doc, str(_TTF), embed_subset=False)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text("AB")
        cs.end_text()
    assert doc.get_fonts_to_subset() == set()
    assert b"(\x00$\x00%) Tj" in page.get_contents()
    with _save_reload(doc) as reloaded:
        assert PDFTextStripper().get_text(reloaded) == "AB\n"
    doc.close()


def test_show_text_records_code_points_for_subset() -> None:
    doc, page = _page_doc()
    font = PDType0Font.load(doc, str(_TTF))
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text("Hé")
        cs.show_text_with_positioning(["x", 5])
        cs.end_text()
    assert {ord("H"), ord("é"), ord("x")} <= font._subset_codepoints
    doc.close()


def test_bytes_input_is_written_unencoded_and_not_tracked() -> None:
    # pypdfbox extension: pre-encoded bytes pass straight through.
    doc, page = _page_doc()
    font = PDType0Font.load(doc, str(_TTF))
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text(font.encode("AB"))
        cs.end_text()
    assert b"(\x00$\x00%) Tj" in page.get_contents()
    assert font._subset_codepoints == set()
    doc.close()


# ------------------------------------------------------------------
# Simple fonts
# ------------------------------------------------------------------


def test_standard14_ascii_bytes_unchanged() -> None:
    doc, page = _page_doc()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(PDType1Font.standard14("Helvetica"), 12)
        cs.show_text("Hello (World) \\")
        cs.end_text()
    assert b"(Hello \\(World\\) \\\\) Tj\n" in page.get_contents()
    doc.close()


def test_standard14_non_ascii_uses_win_ansi_codes() -> None:
    doc, page = _page_doc()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(PDType1Font.standard14("Helvetica"), 12)
        cs.show_text("€éŒ")
        cs.end_text()
    # WinAnsi: Euro 0x80, eacute 0xE9, OE 0x8C. Bytes >= 0x80 -> hex.
    assert b"<80E98C> Tj\n" in page.get_contents()
    doc.close()


def test_standard14_unencodable_character_substitutes_question_mark() -> None:
    # Documented pypdfbox divergence: PDFont.encode substitutes "?" where
    # upstream raises IllegalArgumentException.
    doc, page = _page_doc()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(PDType1Font.standard14("Helvetica"), 12)
        cs.show_text("Ж")
        cs.end_text()
    assert b"(?) Tj\n" in page.get_contents()
    doc.close()


def test_true_type_simple_font_encodes_through_encoding() -> None:
    doc, page = _page_doc()
    font = PDTrueTypeFont.load(doc, str(_TTF), WinAnsiEncoding.INSTANCE)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text("Aé")
        cs.end_text()
    assert b"<41E9> Tj\n" in page.get_contents()
    doc.close()


# ------------------------------------------------------------------
# Guards and set_font bookkeeping
# ------------------------------------------------------------------


def test_font_popped_by_restore_makes_show_text_raise() -> None:
    # Upstream checks fontStack.isEmpty(): a font set inside q/Q is gone
    # after the matching Q.
    doc, page = _page_doc()
    cs = PDPageContentStream(doc, page)
    cs.save_graphics_state()
    cs.set_font(PDType1Font.standard14("Helvetica"), 12)
    cs.restore_graphics_state()
    cs.begin_text()
    with pytest.raises(RuntimeError, match="set_font"):
        cs.show_text("x")
    with pytest.raises(RuntimeError, match="set_font"):
        cs.show_text_with_positioning(["x"])
    cs.end_text()
    cs.close()
    doc.close()


def test_non_embedded_non_standard14_font_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    doc, page = _page_doc()
    font_dict = COSDictionary()
    font_dict.set_name(COSName.TYPE, "Font")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.SUBTYPE, "Type1")  # type: ignore[attr-defined]
    font_dict.set_name(COSName.get_pdf_name("BaseFont"), "SomeFont")
    font = PDType1Font(font_dict)
    with (
        caplog.at_level(logging.WARNING),
        PDPageContentStream(doc, page) as cs,
    ):
        cs.set_font(font, 12)
    assert "isn't embedded" in caplog.text
    doc.close()


def test_subset_font_without_document_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    font = PDType0Font.load(None, str(_TTF))
    cs = PDPatternContentStream(PDTilingPattern())
    with caplog.at_level(logging.WARNING):
        cs.set_font(font, 12)
    assert "without a PDDocument context" in caplog.text
    cs.close()


# ------------------------------------------------------------------
# Sibling writers share the implementation
# ------------------------------------------------------------------


def test_form_appearance_and_pattern_writers_encode_through_font() -> None:
    doc = PDDocument()
    font = PDType0Font.load(doc, str(_TTF))
    form = PDFormXObject(doc)
    appearance = PDAppearanceStream(COSStream())
    pattern = PDTilingPattern()
    writers = [
        (PDFormContentStream(form), form.get_cos_object()),
        (PDAppearanceContentStream(appearance), appearance.get_cos_object()),
        (PDPatternContentStream(pattern), pattern.get_cos_object()),
    ]
    for cs, stream in writers:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.show_text("AB")
        cs.end_text()
        cs.close()
        assert b"(\x00$\x00%) Tj" in stream.to_byte_array()
    doc.close()


def test_abstract_content_stream_encodes_through_font() -> None:
    doc = PDDocument()
    font = PDType0Font.load(doc, str(_TTF))
    out = io.BytesIO()
    cs = PDAbstractContentStream(doc, out, PDResources())
    cs.begin_text()
    cs.set_font(font, 12)
    cs.show_text("AB")
    cs.show_text_with_positioning(["A", -10, "B"])
    cs.end_text()
    body = out.getvalue()
    assert b"(\x00$\x00%) Tj\n" in body
    assert b"[(\x00$)-10 (\x00%)] TJ\n" in body
    assert font in doc.get_fonts_to_subset()
    doc.close()
