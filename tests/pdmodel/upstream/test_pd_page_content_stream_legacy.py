"""Port of pdfbox/src/test/java/org/apache/pdfbox/pdmodel/TestPDPageContentStream.java

Upstream baseline: PDFBox 3.0.7.

Distinct from the newer ``PDPageContentStreamTest`` (ported in
``test_pd_page_content_stream.py`` next door); this is the legacy
``TestPDPageContentStream`` class focused on colour-range validation and
the text-mode operator guards.

``IllegalArgumentException`` (out-of-range colour component) maps to
``ValueError``; ``IllegalStateException`` (path / paint / image operator
inside a BT/ET text block) maps to ``RuntimeError`` — the exceptions
``PDPageContentStream`` actually raises in pypdfbox. ``PDFStreamParser(page)``
maps to ``PDFStreamParser.from_content_stream(page)``. Java ``float``
literals like ``0.1f`` are compared with ``pytest.approx`` since pypdfbox
stores them as 32-bit floats widened to Python ``float``.
"""

from __future__ import annotations

import pytest

from pypdfbox import PDDocument, PDPage
from pypdfbox.contentstream.operator_name import OperatorName
from pypdfbox.cos.cos_dictionary import COSDictionary
from pypdfbox.pdfparser.pdf_stream_parser import PDFStreamParser
from pypdfbox.pdmodel.graphics.image.pd_image_x_object import PDImageXObject
from pypdfbox.pdmodel.graphics.image.pd_inline_image import PDInlineImage
from pypdfbox.pdmodel.graphics.shading.pd_shading_type1 import PDShadingType1
from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.pdmodel.pd_page_content_stream import AppendMode, PDPageContentStream
from pypdfbox.pdmodel.pd_resources import PDResources
from pypdfbox.util.matrix import Matrix


def test_set_cmyk_colors() -> None:
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)

        content_stream = PDPageContentStream(doc, page, AppendMode.OVERWRITE, True)
        # pass a non-stroking color in CMYK color space
        content_stream.set_non_stroking_color(0.1, 0.2, 0.3, 0.4)
        with pytest.raises(ValueError):
            content_stream.set_non_stroking_color(1.1, 0, 0, 0)
        with pytest.raises(ValueError):
            content_stream.set_non_stroking_color(0, 1.1, 0, 0)
        with pytest.raises(ValueError):
            content_stream.set_non_stroking_color(0, 0, 1.1, 0)
        with pytest.raises(ValueError):
            content_stream.set_non_stroking_color(0, 0, 0, 1.1)
        content_stream.close()

        page_tokens = PDFStreamParser.from_content_stream(page).parse()
        assert page_tokens[0].float_value() == pytest.approx(0.1, abs=1e-6)
        assert page_tokens[1].float_value() == pytest.approx(0.2, abs=1e-6)
        assert page_tokens[2].float_value() == pytest.approx(0.3, abs=1e-6)
        assert page_tokens[3].float_value() == pytest.approx(0.4, abs=1e-6)
        assert page_tokens[4].get_name() == OperatorName.NON_STROKING_CMYK

        page = PDPage()
        doc.add_page(page)

        content_stream = PDPageContentStream(doc, page, AppendMode.OVERWRITE, False)
        content_stream.set_stroking_color(0.5, 0.6, 0.7, 0.8)
        with pytest.raises(ValueError):
            content_stream.set_stroking_color(1.1, 0, 0, 0)
        with pytest.raises(ValueError):
            content_stream.set_stroking_color(0, 1.1, 0, 0)
        with pytest.raises(ValueError):
            content_stream.set_stroking_color(0, 0, 1.1, 0)
        with pytest.raises(ValueError):
            content_stream.set_stroking_color(0, 0, 0, 1.1)
        content_stream.close()

        page_tokens = PDFStreamParser.from_content_stream(page).parse()
        assert page_tokens[0].float_value() == pytest.approx(0.5, abs=1e-6)
        assert page_tokens[1].float_value() == pytest.approx(0.6, abs=1e-6)
        assert page_tokens[2].float_value() == pytest.approx(0.7, abs=1e-6)
        assert page_tokens[3].float_value() == pytest.approx(0.8, abs=1e-6)
        assert page_tokens[4].get_name() == OperatorName.STROKING_COLOR_CMYK


def test_set_rg_band_g_colors() -> None:
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)

        content_stream = PDPageContentStream(doc, page, AppendMode.OVERWRITE, True)
        # pass a non-stroking color in RGB and Gray color space
        content_stream.set_non_stroking_color(0.1, 0.2, 0.3)
        content_stream.set_non_stroking_color(0.8)
        with pytest.raises(ValueError):
            content_stream.set_non_stroking_color(1.1, 0, 0)
        with pytest.raises(ValueError):
            content_stream.set_non_stroking_color(0, 1.1, 0)
        with pytest.raises(ValueError):
            content_stream.set_non_stroking_color(0, 0, 1.1)
        with pytest.raises(ValueError):
            content_stream.set_non_stroking_color(1.1)
        content_stream.close()

        page_tokens = PDFStreamParser.from_content_stream(page).parse()
        assert page_tokens[0].float_value() == pytest.approx(0.1, abs=1e-6)
        assert page_tokens[1].float_value() == pytest.approx(0.2, abs=1e-6)
        assert page_tokens[2].float_value() == pytest.approx(0.3, abs=1e-6)
        assert page_tokens[3].get_name() == OperatorName.NON_STROKING_RGB
        assert page_tokens[4].float_value() == pytest.approx(0.8, abs=1e-6)
        assert page_tokens[5].get_name() == OperatorName.NON_STROKING_GRAY

        page = PDPage()
        doc.add_page(page)

        content_stream = PDPageContentStream(doc, page, AppendMode.OVERWRITE, False)
        content_stream.set_stroking_color(0.5, 0.6, 0.7)
        content_stream.set_stroking_color(0.8)
        with pytest.raises(ValueError):
            content_stream.set_stroking_color(1.1, 0, 0)
        with pytest.raises(ValueError):
            content_stream.set_stroking_color(0, 1.1, 0)
        with pytest.raises(ValueError):
            content_stream.set_stroking_color(0, 0, 1.1)
        with pytest.raises(ValueError):
            content_stream.set_stroking_color(1.1)
        content_stream.close()

        page_tokens = PDFStreamParser.from_content_stream(page).parse()
        assert page_tokens[0].float_value() == pytest.approx(0.5, abs=1e-6)
        assert page_tokens[1].float_value() == pytest.approx(0.6, abs=1e-6)
        assert page_tokens[2].float_value() == pytest.approx(0.7, abs=1e-6)
        assert page_tokens[3].get_name() == OperatorName.STROKING_COLOR_RGB
        assert page_tokens[4].float_value() == pytest.approx(0.8, abs=1e-6)
        assert page_tokens[5].get_name() == OperatorName.STROKING_COLOR_GRAY


def test_missing_content_stream() -> None:
    """PDFBOX-3510: missing content stream should not fail."""
    page = PDPage()
    tokens = PDFStreamParser.from_content_stream(page).parse()
    assert len(tokens) == 0


def test_close_contract() -> None:
    """Check that close() can be called twice."""
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        content_stream = PDPageContentStream(doc, page, AppendMode.OVERWRITE, True)
        content_stream.close()
        content_stream.close()


def test_general_graphic_state_operator_text_mode() -> None:
    """Check that general graphics state operators are allowed in text mode."""
    with PDDocument() as doc:
        page = PDPage()
        doc.add_page(page)
        content_stream = PDPageContentStream(doc, page)
        content_stream.begin_text()

        img1 = PDImageXObject(doc)
        img2 = PDInlineImage(COSDictionary(), b"", PDResources())
        with pytest.raises(RuntimeError):
            content_stream.draw_image(img1, 0.0, 0.0, 1.0, 1.0)
        with pytest.raises(RuntimeError):
            content_stream.draw_image(img1, Matrix())
        with pytest.raises(RuntimeError):
            content_stream.draw_image(img2, 0.0, 0.0, 1.0, 1.0)
        with pytest.raises(RuntimeError):
            content_stream.add_rect(0, 0, 1, 1)
        with pytest.raises(RuntimeError):
            content_stream.curve_to(0, 0, 1, 1, 2, 2)
        with pytest.raises(RuntimeError):
            content_stream.curve_to_1(0, 0, 1, 1)
        with pytest.raises(RuntimeError):
            content_stream.curve_to_2(0, 0, 1, 1)
        with pytest.raises(RuntimeError):
            content_stream.move_to(0, 0)
        with pytest.raises(RuntimeError):
            content_stream.line_to(1, 1)
        with pytest.raises(RuntimeError):
            content_stream.shading_fill(PDShadingType1(COSDictionary()))
        with pytest.raises(RuntimeError):
            content_stream.stroke()
        with pytest.raises(RuntimeError):
            content_stream.close_and_stroke()
        with pytest.raises(RuntimeError):
            content_stream.close_and_fill_and_stroke()
        with pytest.raises(RuntimeError):
            content_stream.close_and_fill_and_stroke_even_odd()
        with pytest.raises(RuntimeError):
            content_stream.fill()
        with pytest.raises(RuntimeError):
            content_stream.fill_and_stroke()
        with pytest.raises(RuntimeError):
            content_stream.fill_and_stroke_even_odd()
        with pytest.raises(RuntimeError):
            content_stream.fill_even_odd()
        with pytest.raises(RuntimeError):
            content_stream.close_path()
        with pytest.raises(RuntimeError):
            content_stream.clip()
        with pytest.raises(RuntimeError):
            content_stream.clip_even_odd()

        # J
        content_stream.set_line_cap_style(0)
        # j
        content_stream.set_line_join_style(0)
        # w
        content_stream.set_line_width(10.0)
        # d
        content_stream.set_line_dash_pattern([2, 1], 0.0)
        # M
        content_stream.set_miter_limit(1.0)
        # gs
        content_stream.set_graphics_state_parameters(PDExtendedGraphicsState())
        # ri, i are not supported with a specific setter
        content_stream.end_text()
        content_stream.close()
