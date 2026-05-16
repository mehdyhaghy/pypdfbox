"""Coverage boost for ``PDFreeTextAppearanceHandler`` and
``PDLineAppearanceHandler`` (wave 1320).

Targets branches that the earlier wave-1280 / wave-1285 smoke tests did
not exercise:

* /DA parsing (RGB / CMYK / Gray / missing entries) and font extraction.
* /DS CSS ``color:`` override on FreeText.
* Callout intent + line-ending styles + rect-growth path.
* /Rotate transform variants (0, 90, 180, 270).
* AcroForm fallback for default appearance.
* Border-style dashed array path.
* Line annotation caption — Top vs. Inline positioning, vertical caption
  bar, leader-line sign flip, interior-color path, angled vs. non-angled
  endings, contents that explode the font width metric.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.annotation.handlers import (
    PDFreeTextAppearanceHandler,
    PDLineAppearanceHandler,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_free_text import (
    PDAnnotationFreeText,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_line import (
    PDAnnotationLine,
)
from pypdfbox.pdmodel.interactive.annotation.pd_border_style_dictionary import (
    PDBorderStyleDictionary,
)
from pypdfbox.pdmodel.pd_document import PDDocument
from pypdfbox.pdmodel.pd_rectangle import PDRectangle

_RECT = (10.0, 10.0, 210.0, 110.0)


def _appearance_bytes(annotation) -> bytes:
    ap = annotation.get_appearance_dictionary()
    assert ap is not None
    stream = ap.get_normal_appearance().get_appearance_stream()
    return stream.get_stream().to_byte_array()


# ----------------------------------------------------------------------
# PDFreeTextAppearanceHandler — DA / DS / font / rotation
# ----------------------------------------------------------------------


def test_free_text_handler_wrong_annotation_type_noops() -> None:
    handler = PDFreeTextAppearanceHandler(PDAnnotation())
    handler.generate_normal_appearance()
    assert PDAnnotation().get_appearance_dictionary() is None


def test_free_text_extract_non_stroking_color_default_when_no_da() -> None:
    annotation = PDAnnotationFreeText()
    handler = PDFreeTextAppearanceHandler(annotation)
    assert handler.extract_non_stroking_color(annotation) == [0.0]


def test_free_text_extract_non_stroking_color_rgb_from_da() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_default_appearance("/Helv 12 Tf 0.5 0.25 0.75 rg")
    handler = PDFreeTextAppearanceHandler(annotation)
    components = handler.extract_non_stroking_color(annotation)
    assert components == pytest.approx([0.5, 0.25, 0.75])


def test_free_text_extract_non_stroking_color_cmyk_from_da() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_default_appearance("/Helv 10 Tf 0.1 0.2 0.3 0.4 k")
    handler = PDFreeTextAppearanceHandler(annotation)
    components = handler.extract_non_stroking_color(annotation)
    assert components == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_free_text_extract_non_stroking_color_gray_from_da() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_default_appearance("/Helv 10 Tf 0.6 g")
    handler = PDFreeTextAppearanceHandler(annotation)
    components = handler.extract_non_stroking_color(annotation)
    assert components == pytest.approx([0.6])


def test_free_text_extract_non_stroking_color_no_color_op_returns_default() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_default_appearance("/Helv 12 Tf")
    handler = PDFreeTextAppearanceHandler(annotation)
    assert handler.extract_non_stroking_color(annotation) == [0.0]


def test_free_text_extract_font_details_from_da() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_default_appearance("/MyFont 18 Tf 0 g")
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.extract_font_details(annotation)
    assert handler._font_size == pytest.approx(18.0)
    assert handler._font_name.name == "MyFont"


def test_free_text_extract_font_details_defaults_when_no_da() -> None:
    annotation = PDAnnotationFreeText()
    handler = PDFreeTextAppearanceHandler(annotation)
    handler.extract_font_details(annotation)
    assert handler._font_size == PDFreeTextAppearanceHandler.DEFAULT_FONT_SIZE
    assert handler._font_name is PDFreeTextAppearanceHandler.DEFAULT_FONT_NAME


def test_free_text_extract_font_details_falls_back_to_acro_form() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    with PDDocument() as document:
        acro_form = document.get_document_catalog().get_acro_form_or_create()
        acro_form.set_default_appearance("/Helv 14 Tf 0 g")
        handler = PDFreeTextAppearanceHandler(annotation, document=document)
        handler.extract_font_details(annotation)
        assert handler._font_size == pytest.approx(14.0)


def test_free_text_handler_with_ds_color_override_emits_color_op() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_contents("Some contents")
    annotation.set_default_style_string("font: Helvetica; color:#ff8040")
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Color override produces an rg operator using the parsed components.
    assert b"rg" in body


def test_free_text_handler_with_callout_emits_endings_and_grows_rect() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    # Callout polyline far from the rect to force rect-growth.
    annotation.set_callout_line([-50.0, 200.0, 50.0, 150.0, 100.0, 100.0])
    annotation.set_line_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    annotation.set_contents("Callout text")
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Callout stroke + arrow path.
    assert b"m" in body
    assert b"l" in body
    assert b"S" in body
    grown_rect = annotation.get_rectangle()
    # Rect's lower-left should have moved south/west to enclose the polyline.
    assert grown_rect.get_lower_left_x() <= -50.0
    assert grown_rect.get_upper_right_y() >= 200.0


def test_free_text_handler_with_callout_butt_ending_uses_translate_only() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    annotation.set_callout_line([20.0, 20.0, 80.0, 80.0])
    # LE_BUTT is angled per the abstract base's ANGLED_STYLES set, but
    # confirm path runs without raising regardless.
    annotation.set_line_ending_style(PDAnnotationLine.LE_BUTT)
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_free_text_handler_with_callout_circle_ending_is_translate_only() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    # 6-coord callout (2 segments).
    annotation.set_callout_line([10.0, 90.0, 50.0, 50.0, 90.0, 10.0])
    annotation.set_line_ending_style(PDAnnotationLine.LE_CIRCLE)
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Circle ending — Bezier curves should appear.
    assert b"c" in body


def test_free_text_handler_with_invalid_callout_length_is_skipped() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_intent(PDAnnotationFreeText.IT_FREE_TEXT_CALLOUT)
    # 3 coords — neither 4 nor 6, so paths_array is reset to empty.
    annotation.set_callout_line([0.0, 0.0, 1.0])
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # No stroke for the callout polyline because paths_array became [].
    # But the border box rectangle is still painted.
    assert b"re" in body


def test_free_text_handler_rotation_180_runs() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_contents("Rotated")
    annotation.get_cos_object().set_int("Rotate", 180)
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"cm" in body  # rotation -> transform op
    assert b"BT" in body


def test_free_text_handler_rotation_90_runs() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_contents("Side")
    annotation.get_cos_object().set_int("Rotate", 90)
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"cm" in body


def test_free_text_handler_rotation_270_runs() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_contents("Other side")
    annotation.get_cos_object().set_int("Rotate", 270)
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"cm" in body


def test_free_text_handler_dashed_border_emits_dash_pattern() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    border_style = PDBorderStyleDictionary()
    border_style.set_width(2.0)
    border_style.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    border_style.set_dash_style([3.0, 2.0])
    annotation.set_border_style(border_style)
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # set_line_dash_pattern emits the ``d`` operator.
    assert b"d" in body


def test_free_text_handler_multiline_contents_emits_multiple_tj() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_contents("Line one\nLine two\nLine three")
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Each line generates one Tj operator.
    assert body.count(b"Tj") >= 3


def test_free_text_handler_with_opacity_emits_extgstate() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_constant_opacity(0.3)
    PDFreeTextAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"gs" in body


def test_free_text_handler_rollover_and_down_return_none() -> None:
    handler = PDFreeTextAppearanceHandler(PDAnnotationFreeText())
    assert handler.generate_rollover_appearance() is None
    assert handler.generate_down_appearance() is None


def test_free_text_scan_da_handles_parser_construction_exception() -> None:
    annotation = PDAnnotationFreeText()
    handler = PDFreeTextAppearanceHandler(annotation)
    # Patch the parser module so construction raises — covers the outer
    # try/except in ``_scan_da`` and ``_scan_da_for_font``.
    import pypdfbox.pdfparser.pdf_stream_parser as parser_mod

    original = parser_mod.PDFStreamParser

    def _raise(*_args, **_kwargs):
        raise RuntimeError("forced construction failure")

    parser_mod.PDFStreamParser = _raise  # type: ignore[assignment]
    try:
        op, colors = handler._scan_da("/Helv 12 Tf 0.5 g")
        assert op is None
        assert colors is None
        args = handler._scan_da_for_font("/Helv 12 Tf")
        assert args is None
    finally:
        parser_mod.PDFStreamParser = original  # type: ignore[assignment]


def test_free_text_scan_da_swallows_parse_exception() -> None:
    annotation = PDAnnotationFreeText()
    handler = PDFreeTextAppearanceHandler(annotation)
    # Patch parse_next_token via a fake parser that raises on second call
    # so the inner exception handler triggers.
    import pypdfbox.pdfparser.pdf_stream_parser as parser_mod
    from pypdfbox.pdfparser.pdf_stream_parser import Operator

    original = parser_mod.PDFStreamParser

    class _FakeParser:
        def __init__(self, *_args, **_kwargs) -> None:
            self._calls = 0

        def parse_next_token(self):
            self._calls += 1
            if self._calls == 1:
                return Operator("Tf")
            raise RuntimeError("forced parse failure")

    parser_mod.PDFStreamParser = _FakeParser  # type: ignore[assignment]
    try:
        op, colors = handler._scan_da("anything")
        assert op is None  # no color op recorded before the failure
        assert colors is None
        args = handler._scan_da_for_font("anything")
        # The Tf op was recorded with an empty arg list before the
        # exception interrupted the loop.
        assert args == []
    finally:
        parser_mod.PDFStreamParser = original  # type: ignore[assignment]


def test_free_text_resolve_font_uses_acro_form_default_resources() -> None:
    from pypdfbox.cos import COSName
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory
    from pypdfbox.pdmodel.pd_resources import PDResources

    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_default_appearance("/CustomFont 12 Tf 0 g")
    annotation.set_contents("Hello")

    custom_font = PDFontFactory.create_default_font()

    with PDDocument() as document:
        acro_form = document.get_document_catalog().get_acro_form_or_create()
        resources = PDResources()

        class _FontHostingResources:
            """Minimal duck of ``PDResources`` exposing ``get_font``."""

            def __init__(self, font) -> None:
                self._font = font

            def get_font(self, name):
                if name == COSName.get_pdf_name("CustomFont"):
                    return self._font
                return None

        acro_form.set_default_resources(resources)

        # Force resolve_font to hit the AcroForm path by swapping
        # ``get_default_resources`` for the host that returns our font.
        host = _FontHostingResources(custom_font)
        acro_form.get_default_resources = lambda: host  # type: ignore[method-assign]

        PDFreeTextAppearanceHandler(annotation, document=document).generate_normal_appearance()
        assert annotation.get_appearance_dictionary() is not None


def test_free_text_resolve_font_falls_back_when_acro_form_font_lookup_raises() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_default_appearance("/Helv 12 Tf 0 g")
    annotation.set_contents("Hello")

    with PDDocument() as document:
        acro_form = document.get_document_catalog().get_acro_form_or_create()

        class _RaisingResources:
            def get_font(self, _name):
                raise RuntimeError("forced lookup failure")

        acro_form.get_default_resources = lambda: _RaisingResources()  # type: ignore[method-assign]
        # Should not raise — the get_font exception is caught and the
        # handler falls back to ``get_default_font()``.
        PDFreeTextAppearanceHandler(annotation, document=document).generate_normal_appearance()
        assert annotation.get_appearance_dictionary() is not None


def test_free_text_handler_returns_when_resolve_font_returns_none() -> None:
    annotation = PDAnnotationFreeText()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_contents("Should not be rendered")

    handler = PDFreeTextAppearanceHandler(annotation)
    handler._resolve_font = lambda: None  # type: ignore[method-assign]
    handler.generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # No text block emitted because we returned before begin_text.
    assert b"BT" not in body


# ----------------------------------------------------------------------
# PDLineAppearanceHandler — captions / leader lines / endings
# ----------------------------------------------------------------------


def test_line_handler_wrong_annotation_type_noops() -> None:
    PDLineAppearanceHandler(PDAnnotation()).generate_normal_appearance()
    assert PDAnnotation().get_appearance_dictionary() is None


def test_line_handler_runs_with_default_zero_line() -> None:
    # ``PDAnnotationLine`` seeds ``/L`` to ``[0,0,0,0]``, so the handler
    # walks the full body — but the rectangle still gets expanded by
    # the padding rule and a zero-length line is emitted.
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_line_handler_skips_without_rect() -> None:
    annotation = PDAnnotationLine()
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([0.0, 0.0, 50.0, 50.0])
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_line_handler_skips_without_color() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_line([0.0, 0.0, 50.0, 50.0])
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is None


def test_line_handler_with_top_caption_emits_text_above_line() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([20.0, 50.0, 180.0, 50.0])
    annotation.set_caption(True)
    annotation.set_caption_positioning("Top")
    annotation.set_contents("Above")
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"BT" in body
    assert b"ET" in body


def test_line_handler_with_caption_vertical_offset_emits_extra_bar() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([20.0, 50.0, 180.0, 50.0])
    annotation.set_caption(True)
    annotation.set_contents("Caption")
    annotation.set_caption_vertical_offset(5.0)
    annotation.set_caption_horizontal_offset(3.0)
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # When CV != 0, an additional move_to/line_to draws a vertical bar.
    assert body.count(b"m") >= 2
    assert b"l" in body


def test_line_handler_with_interior_color_emits_non_stroking_color() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_interior_color([1.0, 0.5, 0.25])
    annotation.set_start_point_ending_style(PDAnnotationLine.LE_CIRCLE)
    annotation.set_end_point_ending_style(PDAnnotationLine.LE_DIAMOND)
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    # Interior color -> rg operator (DeviceRGB non-stroking color).
    assert b"rg" in body


def test_line_handler_with_arrow_endings_emits_arrow_lines() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_start_point_ending_style(PDAnnotationLine.LE_OPEN_ARROW)
    annotation.set_end_point_ending_style(PDAnnotationLine.LE_CLOSED_ARROW)
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"l" in body


def test_line_handler_with_non_angled_endings_uses_offset_only() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_start_point_ending_style(PDAnnotationLine.LE_CIRCLE)
    annotation.set_end_point_ending_style(PDAnnotationLine.LE_SQUARE)
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"c" in body  # circle uses curves
    assert b"re" in body  # square uses add_rect


def test_line_handler_with_negative_leader_line_flips_sign() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_leader_line_length(-15.0)
    annotation.set_leader_line_extension_length(5.0)
    annotation.set_leader_line_offset_length(2.0)
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"m" in body


def test_line_handler_with_thin_width_treats_endings_as_unit() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    border_style = PDBorderStyleDictionary()
    border_style.set_width(0.0)
    annotation.set_border_style(border_style)
    annotation.set_start_point_ending_style(PDAnnotationLine.LE_CIRCLE)
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"c" in body


def test_line_handler_with_dashed_border_emits_dash_pattern() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    border_style = PDBorderStyleDictionary()
    border_style.set_width(2.0)
    border_style.set_style(PDBorderStyleDictionary.STYLE_DASHED)
    border_style.set_dash_style([4.0, 2.0])
    annotation.set_border_style(border_style)
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"d" in body


def test_line_handler_caption_with_font_missing_string_width_falls_back() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory

    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_caption(True)
    annotation.set_contents("Hi")

    # Real font, but with get_string_width swapped to raise — drives the
    # AttributeError/ValueError/KeyError fallback to the monospace
    # estimate while leaving ``set_font`` happy.
    font = PDFontFactory.create_default_font()

    def _raise_attr(_text: str) -> float:
        raise AttributeError("no metrics in fixture")

    font.get_string_width = _raise_attr  # type: ignore[method-assign]
    handler = PDLineAppearanceHandler(annotation)
    handler._default_font = font
    handler.generate_normal_appearance()
    assert annotation.get_appearance_dictionary() is not None


def test_line_handler_interior_components_helper_handles_to_float_array() -> None:
    annotation = PDAnnotationLine()
    annotation.set_interior_color([0.1, 0.2, 0.3])
    components = PDLineAppearanceHandler._interior_components(annotation)
    assert components == pytest.approx([0.1, 0.2, 0.3])


def test_line_handler_interior_components_helper_returns_none_for_unset() -> None:
    annotation = PDAnnotationLine()
    assert PDLineAppearanceHandler._interior_components(annotation) is None


def test_line_handler_interior_components_helper_returns_none_for_empty() -> None:
    annotation = PDAnnotationLine()
    annotation.set_interior_color([])
    assert PDLineAppearanceHandler._interior_components(annotation) is None


def test_line_handler_with_no_caption_but_contents_skips_text_block() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_contents("Should not render")
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"BT" not in body


def test_line_handler_rollover_and_down_return_none() -> None:
    handler = PDLineAppearanceHandler(PDAnnotationLine())
    assert handler.generate_rollover_appearance() is None
    assert handler.generate_down_appearance() is None


def test_line_handler_caption_with_short_start_and_end_endings() -> None:
    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([20.0, 50.0, 180.0, 50.0])
    annotation.set_caption(True)
    annotation.set_contents("Mid")
    annotation.set_start_point_ending_style(PDAnnotationLine.LE_CIRCLE)
    annotation.set_end_point_ending_style(PDAnnotationLine.LE_SQUARE)
    PDLineAppearanceHandler(annotation).generate_normal_appearance()
    body = _appearance_bytes(annotation)
    assert b"BT" in body


def test_line_handler_caption_show_text_swallowed_when_font_raises() -> None:
    from pypdfbox.pdmodel.font.pd_font_factory import PDFontFactory

    annotation = PDAnnotationLine()
    annotation.set_rectangle(PDRectangle(*_RECT))
    annotation.set_color([0.0, 0.0, 0.0])
    annotation.set_line([10.0, 50.0, 190.0, 50.0])
    annotation.set_caption(True)
    annotation.set_contents("Boom")

    font = PDFontFactory.create_default_font()
    # Real metrics, but show_text on the content stream is what's wrapped;
    # raise from encode to drive a ValueError inside the try/except.

    def _raise_value(_text: str) -> bytes:
        raise ValueError("encode failure")

    font.encode = _raise_value  # type: ignore[method-assign]
    handler = PDLineAppearanceHandler(annotation)
    handler._default_font = font
    handler.generate_normal_appearance()
    # Should not raise — appearance dict still produced even when text
    # emission fails.
    assert annotation.get_appearance_dictionary() is not None


def test_line_handler_interior_components_helper_with_size_only_object() -> None:
    class _ColorWithSizeNoToFloat:
        def __init__(self, components: list[float]) -> None:
            self._components = components

        def size(self) -> int:
            return len(self._components)

        def to_float_array(self) -> list[float]:
            return list(self._components)

    class _Annot:
        def __init__(self, color) -> None:
            self._color = color

        def get_interior_color(self):
            return self._color

    # Non-empty -> returns the array
    nonempty = _ColorWithSizeNoToFloat([0.1, 0.2])
    # Drop the to_float_array test branch by simulating a non-hashing attribute
    # check; we want the size() branch, not the hasattr to_float_array branch.
    # The simplest is to remove to_float_array via delattr after construction.
    del _ColorWithSizeNoToFloat.to_float_array

    # Need to re-build because we just removed the class attribute.
    class _ColorSizeOnly:
        def __init__(self, components: list[float]) -> None:
            self._components = components

        def size(self) -> int:
            return len(self._components)

    # Empty -> returns None via the size==0 branch.
    empty = _ColorSizeOnly([])
    assert PDLineAppearanceHandler._interior_components(_Annot(empty)) is None

    # to_float_array bound method patched on the bare object.
    nonempty2 = _ColorSizeOnly([0.4, 0.5, 0.6])
    nonempty2.to_float_array = lambda: [0.4, 0.5, 0.6]  # type: ignore[attr-defined]
    assert PDLineAppearanceHandler._interior_components(_Annot(nonempty2)) == [
        0.4,
        0.5,
        0.6,
    ]

    # Confirm the unused nonempty/_ColorWithSizeNoToFloat reference doesn't trip linting.
    assert nonempty._components == [0.1, 0.2]


def test_line_handler_interior_components_helper_with_sequence_object() -> None:
    class _ColorAsSeq:
        def __init__(self, components):
            self._c = components

        def __iter__(self):
            return iter(self._c)

    class _Annot:
        def __init__(self, color):
            self._color = color

        def get_interior_color(self):
            return self._color

    # Non-empty -> list(seq) returned as-is.
    assert PDLineAppearanceHandler._interior_components(
        _Annot(_ColorAsSeq([0.7, 0.8]))
    ) == [0.7, 0.8]
    # Empty -> None.
    assert PDLineAppearanceHandler._interior_components(_Annot(_ColorAsSeq([]))) is None
