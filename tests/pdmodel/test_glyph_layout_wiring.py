"""PDFBOX-4951 glyph-layout wiring — core-only behaviour.

Upstream split the feature in two: the *core* (interfaces plus the
``PDAbstractContentStream`` / ``PDAcroForm`` / ``AppearanceGeneratorHelper``
wiring, shipped inside the ``pdfbox`` artifact) and an *optional* shaping
backend in a separate Maven module. pypdfbox ports the core only, so the two
things that must hold are:

1. with **no** processor registered — the default, and the only shape the
   library ships — every byte the content-stream writers emit is exactly what
   they emitted before the feature landed; and
2. with a processor registered, the plug-in point actually reaches the writer
   end to end.

Both are asserted below against golden operator bytes.
"""

import io
from typing import Any

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel import (
    PDAbstractContentStream,
    PDDocument,
    PDPage,
    PDRectangle,
    PDResources,
)
from pypdfbox.pdmodel.font import PDType1Font
from pypdfbox.pdmodel.font.pd_type0_font import PDType0Font
from pypdfbox.pdmodel.glyph_layout_processor_interface import (
    GlyphLayoutProcessorInterface,
)
from pypdfbox.pdmodel.glyphs_and_positions import GlyphsAndPositions
from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm
from pypdfbox.pdmodel.pd_page_content_stream import PDPageContentStream


class _Concrete(PDAbstractContentStream):
    """Minimal concrete subclass, as used by the other base-class tests."""


class _FakeFont:
    """Latin-1 encoder stand-in (matches the existing base-class tests)."""

    def encode(self, text: str) -> bytes:
        return text.encode("latin-1")


class _StubProcessor(GlyphLayoutProcessorInterface):
    """Backend-free ``GlyphLayoutProcessorInterface`` implementation.

    It claims :class:`PDType0Font` instances (like a real backend would) and
    emits a fixed, easily-asserted glyph run so the plug-in point can be
    verified without a shaping library.
    """

    def __init__(self, supports: bool = True) -> None:
        self.supports = supports
        self.calls: list[tuple[Any, float, str]] = []

    def supports_font(self, font: Any) -> bool:
        return self.supports and isinstance(font, PDType0Font)

    def get_string_width(self, font: Any, font_size: float, text: str) -> float:
        return len(text) * font_size

    def show_text(
        self, content_stream: Any, font: Any, font_size: float, text: str
    ) -> None:
        self.calls.append((font, font_size, text))
        gap = GlyphsAndPositions()
        gap.add(3)
        gap.add(4)
        gap.add(-120.0)
        gap.add(5)
        content_stream.show_glyphs_with_positioning(gap)


def _make_abstract(
    resources: PDResources | None = None,
) -> tuple[_Concrete, io.BytesIO]:
    out = io.BytesIO()
    return _Concrete(None, out, resources), out


def _make_page(doc: PDDocument) -> PDPage:
    page = PDPage(PDRectangle(0.0, 0.0, 200.0, 200.0))
    doc.add_page(page)
    return page


def _make_type1_font() -> PDType1Font:
    font = PDType1Font()
    font.get_cos_object().set_name(COSName.get_pdf_name("BaseFont"), "Helvetica")
    return font


# ==================================================================
# 1. Default path (no processor) — byte-identical output
# ==================================================================


def test_abstract_show_text_without_processor_is_unchanged() -> None:
    cs, out = _make_abstract()
    cs._font_stack.append(_FakeFont())
    cs._font_size_stack.append(12.0)
    cs.begin_text()
    out.seek(0)
    out.truncate()
    cs.show_text("AB")
    assert out.getvalue() == b"<4142> Tj\n"


def test_abstract_show_text_with_positioning_without_processor_is_unchanged() -> None:
    cs, out = _make_abstract()
    cs._font_stack.append(_FakeFont())
    cs._font_size_stack.append(12.0)
    cs.begin_text()
    out.seek(0)
    out.truncate()
    cs.show_text_with_positioning(["A", -120, "B"])
    assert out.getvalue() == b"[<41>-120 <42>] TJ\n"


def test_abstract_set_font_bytes_unchanged() -> None:
    resources = PDResources()
    cs, out = _make_abstract(resources)
    cs.set_font(_make_type1_font(), 12)
    assert out.getvalue() == b"/F1 12 Tf\n"


def test_page_stream_show_text_without_processor_is_unchanged() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_type1_font(), 12)
        cs.show_text("hi")
        cs.end_text()
    body = page.get_contents()
    assert b"BT\n" in body
    assert b"/F1 12 Tf\n" in body
    assert b"(hi) Tj\n" in body
    assert b"ET\n" in body


def test_page_stream_processor_that_rejects_the_font_changes_nothing() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    processor = _StubProcessor()
    with PDPageContentStream(doc, page) as cs:
        cs.set_glyph_layout_processor(processor)
        cs.begin_text()
        # A simple font is not a PDType0Font, so the stub declines it and the
        # ordinary encode path runs.
        cs.set_font(_make_type1_font(), 12)
        cs.show_text("hi")
        cs.end_text()
    assert b"(hi) Tj\n" in page.get_contents()
    assert processor.calls == []


def test_page_stream_q_Q_bytes_unchanged() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.save_graphics_state()
        cs.restore_graphics_state()
    body = page.get_contents()
    assert b"q\nQ\n" in body


def test_font_stack_follows_q_Q() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    font = _make_type1_font()
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(font, 12)
        cs.end_text()
        assert list(cs._font_stack) == [font]
        cs.save_graphics_state()
        assert list(cs._font_stack) == [font, font]
        cs.restore_graphics_state()
        assert list(cs._font_stack) == [font]


# ==================================================================
# 2. Plug-in point — end to end through a stub backend
# ==================================================================


def test_abstract_processor_drives_show_text() -> None:
    resources = PDResources()
    cs, out = _make_abstract(resources)
    processor = _StubProcessor()
    cs.set_glyph_layout_processor(processor)
    font = PDType0Font()
    cs.begin_text()
    cs.set_font(font, 14.0)
    out.seek(0)
    out.truncate()
    cs.show_text("ab")
    assert processor.calls == [(font, 14.0, "ab")]
    # glyph 3/4 -> 0x0003 0x0004, glyph 5 -> 0x0005; COSWriter emits the
    # literal form because every byte is ASCII-range and not CR/LF.
    assert out.getvalue() == b"[(\x00\x03\x00\x04)-120 (\x00\x05)] TJ\n"


def test_page_stream_processor_drives_show_text() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    processor = _StubProcessor()
    font = PDType0Font()
    with PDPageContentStream(doc, page) as cs:
        cs.set_glyph_layout_processor(processor)
        cs.begin_text()
        cs.set_font(font, 14.0)
        cs.show_text("ab")
        cs.end_text()
    assert processor.calls == [(font, 14.0, "ab")]
    assert b"[(\x00\x03\x00\x04)-120 (\x00\x05)] TJ\n" in page.get_contents()


def test_setting_the_processor_to_none_restores_the_default_path() -> None:
    cs, out = _make_abstract()
    cs.set_glyph_layout_processor(_StubProcessor())
    cs.set_glyph_layout_processor(None)
    cs.begin_text()
    cs.set_font(_FakeFont(), 12.0)
    out.seek(0)
    out.truncate()
    cs.show_text("AB")
    assert out.getvalue() == b"<4142> Tj\n"


# ==================================================================
# 3. show_glyph_codes / write_text_pd_type0_font
# ==================================================================


def test_abstract_show_glyph_codes() -> None:
    cs, out = _make_abstract(PDResources())
    cs.begin_text()
    cs.set_font(PDType0Font(), 11.0)
    out.seek(0)
    out.truncate()
    cs.show_glyph_codes([3, 4])
    assert out.getvalue() == b"(\x00\x03\x00\x04) Tj\n"


def test_page_stream_show_glyph_codes() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(PDType0Font(), 11.0)
        cs.show_glyph_codes([3, 4])
        cs.end_text()
    assert b"(\x00\x03\x00\x04) Tj\n" in page.get_contents()


def test_glyph_codes_require_a_type0_font() -> None:
    cs, _ = _make_abstract(PDResources())
    cs.begin_text()
    cs.set_font(_make_type1_font(), 11.0)
    with pytest.raises(RuntimeError, match="PDType0Font"):
        cs.show_glyph_codes([3])


def test_glyph_codes_require_text_mode() -> None:
    cs, _ = _make_abstract(PDResources())
    with pytest.raises(RuntimeError):
        cs.show_glyph_codes([3])


def test_glyph_codes_require_a_font() -> None:
    cs, _ = _make_abstract(PDResources())
    cs.begin_text()
    with pytest.raises(RuntimeError):
        cs.show_glyph_codes([3])


def test_page_stream_glyph_codes_require_a_type0_font() -> None:
    doc = PDDocument()
    page = _make_page(doc)
    with PDPageContentStream(doc, page) as cs:
        cs.begin_text()
        cs.set_font(_make_type1_font(), 11.0)
        with pytest.raises(RuntimeError, match="PDType0Font"):
            cs.show_glyph_codes([3])
        cs.end_text()


def test_glyphs_with_positioning_rejects_foreign_entries() -> None:
    cs, _ = _make_abstract(PDResources())
    cs.begin_text()
    cs.set_font(PDType0Font(), 11.0)
    gap = GlyphsAndPositions()
    gap._list.append(object())
    with pytest.raises(ValueError, match="GlyphSubList"):
        cs.show_glyphs_with_positioning(gap)


def test_glyphs_with_positioning_rejects_none_entries() -> None:
    cs, _ = _make_abstract(PDResources())
    cs.begin_text()
    cs.set_font(PDType0Font(), 11.0)
    gap = GlyphsAndPositions()
    gap._list.append(None)
    with pytest.raises(TypeError, match="null entry"):
        cs.show_glyphs_with_positioning(gap)


def test_glyph_ids_above_the_bmp_limit_are_not_added_to_the_subset() -> None:
    cs, _ = _make_abstract(PDResources())
    font = PDType0Font()
    font._will_be_subset = True
    cs.begin_text()
    cs.set_font(font, 11.0)
    cs.show_glyph_codes([7, 0xFFFF, 9])
    assert font._subset_glyph_ids == {7, 9}


# ==================================================================
# 4. PDAcroForm accessors + AppearanceGeneratorHelper lookup
# ==================================================================


def test_acro_form_processor_defaults_to_none() -> None:
    assert PDAcroForm().get_glyph_layout_processor() is None


def test_acro_form_processor_round_trips() -> None:
    form = PDAcroForm()
    processor = _StubProcessor()
    form.set_glyph_layout_processor(processor)
    assert form.get_glyph_layout_processor() is processor
    form.set_glyph_layout_processor(None)
    assert form.get_glyph_layout_processor() is None


def test_appearance_generator_picks_up_the_acro_form_processor() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
        PDAppearanceGenerator,
    )
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

    doc = PDDocument()
    page = _make_page(doc)
    form = PDAcroForm(doc)
    processor = _StubProcessor()
    form.set_glyph_layout_processor(processor)

    field = PDTextField(form)
    field.set_partial_name("t1")
    widget = field.get_widgets()[0]
    widget.set_rectangle(PDRectangle(10.0, 10.0, 100.0, 20.0))
    widget.set_page(page)

    generator = PDAppearanceGenerator()
    generator.generate(field)
    assert generator._acro_form_glyph_layout_processor is processor


def test_appearance_generator_helper_exposes_the_form_processor() -> None:
    from pypdfbox.pdmodel.interactive.form.appearance_generator_helper import (
        AppearanceGeneratorHelper,
    )
    from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

    form = PDAcroForm(PDDocument())
    processor = _StubProcessor()
    form.set_glyph_layout_processor(processor)
    field = PDTextField(form)
    field.set_partial_name("t1")

    helper = AppearanceGeneratorHelper(field)
    assert helper.get_glyph_layout_processor() is processor

    form.set_glyph_layout_processor(None)
    assert AppearanceGeneratorHelper(field).get_glyph_layout_processor() is None
