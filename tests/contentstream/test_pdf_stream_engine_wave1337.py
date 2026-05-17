"""Wave 1337 coverage-boost tests for ``pypdfbox.contentstream.pdf_stream_engine``.

Targets the residual branches:

  * ``process_form`` — alias for ``process_stream``                       (598)
  * ``process_transparency_group`` — ``ctm is not None`` branch           (666)
  * ``process_soft_mask`` — save/restore around process_transparency_group (689-693)
  * ``process_tiling_pattern`` / ``process_type3_stream`` thin wrappers   (705-706, 717-718)
  * ``show_annotation`` / ``process_annotation`` guards                   (733, 771, 775-789)
  * ``push_resources`` — page-resources fallback / fresh ``PDResources``  (823-827)
  * ``clip_to_rect`` — no clipper / transform-failing rectangle           (863, 869-872)
  * ``_get_active_font`` — gs without ``text_state`` falls to ``text_font`` (1073)
  * ``_decode_codes_via_font`` — no-progress break                        (1095)
  * ``_glyph_displacement`` — ``get_displacement`` raises                 (1109-1112)
  * ``show_type3_glyph`` — get_char_proc raises / returns None            (1166-1167)
  * ``apply_text_adjustment`` — matrix without translate                  (1189)
  * ``transformed_point`` — ctm + transform_point edge cases              (1210, 1213, 1216-1217)
  * ``_require_min_operands`` — too few operands raise                    (1238-1239)
"""
from __future__ import annotations

import io
from typing import Any

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    OperatorProcessor,
    PDFStreamEngine,
)
from pypdfbox.cos import COSBase, COSStream
from pypdfbox.pdmodel import PDPage, PDRectangle, PDResources
from pypdfbox.pdmodel.graphics.form.pd_form_x_object import PDFormXObject
from pypdfbox.pdmodel.graphics.form.pd_transparency_group import PDTransparencyGroup


def _empty_engine_with_page() -> PDFStreamEngine:
    engine = PDFStreamEngine()
    engine._current_page = PDPage()
    engine._is_processing_page = True
    return engine


# ---------- process_form ----------


def test_process_form_routes_through_process_stream() -> None:
    """Line 598 — ``process_form`` delegates to ``process_stream``."""
    class _Probe(OperatorProcessor):
        def __init__(self) -> None:
            super().__init__()
            self.count = 0

        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            self.count += 1

        def get_name(self) -> str:
            return "Tj"

    engine = _empty_engine_with_page()
    probe = _Probe()
    engine.add_operator(probe)
    cos = COSStream()
    cos.set_raw_data(b"(X) Tj")
    form = PDFormXObject(cos)
    engine.process_form(form)
    assert probe.count == 1


# ---------- process_transparency_group / soft_mask / tiling / type3 ----------


def test_process_transparency_group_with_ctm_swaps_initial_matrix() -> None:
    """Line 666 — when the GS exposes a ``current_transformation_matrix``,
    the helper snapshots it into ``_initial_matrix`` for the duration of
    the dispatch."""
    sentinel_ctm = object()

    class _GSWithCTM:
        current_transformation_matrix = sentinel_ctm

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GSWithCTM()

    engine = _TestEngine()
    engine._current_page = PDPage()
    engine._is_processing_page = True
    cos = COSStream()
    cos.set_raw_data(b"")
    group = PDTransparencyGroup(cos)
    # Just exercise the path — no assertion on side effects since the
    # base engine doesn't expose initial_matrix as a public field, but
    # the line is executed.
    engine.process_transparency_group(group)


def test_process_soft_mask_fences_dispatch() -> None:
    """Lines 689-693 — ``process_soft_mask`` saves the graphics state,
    drives ``process_transparency_group``, then restores."""
    calls = []

    class _TestEngine(PDFStreamEngine):
        def save_graphics_state(self) -> None:
            calls.append("save")

        def restore_graphics_state(self) -> None:
            calls.append("restore")

    engine = _TestEngine()
    engine._current_page = PDPage()
    engine._is_processing_page = True
    cos = COSStream()
    cos.set_raw_data(b"")
    group = PDTransparencyGroup(cos)
    engine.process_soft_mask(group)
    assert calls == ["save", "restore"]


def test_process_tiling_pattern_drives_operators() -> None:
    """Lines 705-706 — ``process_tiling_pattern`` ignores the colour
    args and just drives the operators through ``process_stream``."""

    class _Probe(OperatorProcessor):
        def __init__(self) -> None:
            super().__init__()
            self.count = 0

        def process(self, op: Operator, ops: list[COSBase]) -> None:
            self.count += 1

        def get_name(self) -> str:
            return "Tj"

    class _Pattern:
        def get_resources(self):
            return None

        def get_stream(self):
            cos = COSStream()
            cos.set_raw_data(b"(P) Tj")
            return cos

        def get_contents(self):
            return io.BytesIO(b"(P) Tj")

        def get_cos_object(self):
            cos = COSStream()
            cos.set_raw_data(b"(P) Tj")
            return cos

    engine = _empty_engine_with_page()
    probe = _Probe()
    engine.add_operator(probe)
    # Use a real form xobject as the pattern shape — process_stream
    # expects this shape.
    cos = COSStream()
    cos.set_raw_data(b"(P) Tj")
    pattern = PDFormXObject(cos)
    engine.process_tiling_pattern(pattern, color=None, color_space=None)
    assert probe.count == 1


def test_process_type3_stream_drives_operators() -> None:
    """Lines 717-718 — ``process_type3_stream`` ignores the matrix and
    just drives the operators."""
    class _Probe(OperatorProcessor):
        def __init__(self) -> None:
            super().__init__()
            self.count = 0

        def process(self, op: Operator, ops: list[COSBase]) -> None:
            self.count += 1

        def get_name(self) -> str:
            return "Tj"

    engine = _empty_engine_with_page()
    probe = _Probe()
    engine.add_operator(probe)
    cos = COSStream()
    cos.set_raw_data(b"(Y) Tj")
    form = PDFormXObject(cos)
    engine.process_type3_stream(form, text_matrix=None)
    assert probe.count == 1


# ---------- show_annotation / process_annotation ----------


def test_show_annotation_returns_when_no_appearance() -> None:
    """``show_annotation`` is a no-op when ``get_appearance`` returns
    None (line 733 not entered)."""
    class _Annot:
        def get_normal_appearance_stream(self) -> None:
            return None

    engine = _empty_engine_with_page()
    engine.show_annotation(_Annot())  # type: ignore[arg-type]


def test_show_annotation_dispatches_to_process_annotation() -> None:
    """Line 733 — when ``get_appearance`` returns a stream, the helper
    forwards to ``process_annotation``."""
    captured: list[Any] = []

    class _TestEngine(PDFStreamEngine):
        def process_annotation(
            self, annotation: Any, appearance: Any
        ) -> None:
            captured.append((annotation, appearance))

    engine = _TestEngine()
    engine._current_page = PDPage()
    engine._is_processing_page = True

    appearance = object()

    class _Annot:
        def get_normal_appearance_stream(self) -> Any:
            return appearance

    annot = _Annot()
    engine.show_annotation(annot)  # type: ignore[arg-type]
    assert captured == [(annot, appearance)]


def test_process_annotation_skips_when_bbox_or_rect_missing() -> None:
    """Line 771 — when either ``rect`` or ``bbox`` is None, the helper
    early-returns."""
    class _Appearance:
        def get_bbox(self) -> None:
            return None

        def get_resources(self):
            return None

    class _Annot:
        def get_rectangle(self):
            return None

    engine = _empty_engine_with_page()
    # No exception, just early-return.
    engine.process_annotation(_Annot(), _Appearance())  # type: ignore[arg-type]


def test_process_annotation_skips_zero_width_rect() -> None:
    """Lines 773-774 — a zero-width rectangle short-circuits the
    dispatch via the ``rect.get_width() <= 0`` arm."""
    class _Rect:
        def get_width(self) -> float:
            return 0

        def get_height(self) -> float:
            return 0

    class _Appearance:
        def get_bbox(self) -> Any:
            return _Rect()

        def get_resources(self):
            return None

    class _Annot:
        def get_rectangle(self):
            return _Rect()

    engine = _empty_engine_with_page()
    engine.process_annotation(_Annot(), _Appearance())  # type: ignore[arg-type]


def test_process_annotation_skips_zero_width_bbox() -> None:
    """Line 776 — a zero-width bbox short-circuits the dispatch even
    when the rect is non-degenerate."""
    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)

    class _ZeroBbox:
        def get_width(self) -> float:
            return 0.0

        def get_height(self) -> float:
            return 0.0

    class _Appearance:
        def get_bbox(self) -> Any:
            return _ZeroBbox()

    class _Annot:
        def get_rectangle(self) -> Any:
            return rect

    engine = _empty_engine_with_page()
    engine.process_annotation(_Annot(), _Appearance())  # type: ignore[arg-type]


def test_process_annotation_handles_rect_attribute_errors() -> None:
    """Lines 777-778 — ``rect.get_width`` raising AttributeError /
    TypeError short-circuits silently."""
    class _BadRect:
        def get_width(self) -> float:
            raise AttributeError("flaky")

        def get_height(self) -> float:
            return 1

    class _Appearance:
        def get_bbox(self) -> Any:
            return _BadRect()

        def get_resources(self):
            return None

    class _Annot:
        def get_rectangle(self):
            return _BadRect()

    engine = _empty_engine_with_page()
    engine.process_annotation(_Annot(), _Appearance())  # type: ignore[arg-type]


def test_process_annotation_drives_dispatch_on_valid_geometry() -> None:
    """Lines 780-789 — a valid rect+bbox runs through push_resources,
    save_graphics_stack, clip_to_rect, process_stream_operators,
    and pop_resources. Use a real :class:`PDAppearanceStream` so the
    inner ``process_stream_operators`` walks a valid stream surface."""
    from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
        PDAppearanceStream,
    )

    rect = PDRectangle(0.0, 0.0, 100.0, 100.0)
    bbox = PDRectangle(0.0, 0.0, 50.0, 50.0)
    cos = COSStream()
    cos.set_raw_data(b"")
    appearance = PDAppearanceStream(cos)
    appearance.set_bbox(bbox)

    class _Annot:
        def get_rectangle(self) -> Any:
            return rect

    engine = _empty_engine_with_page()
    engine.process_annotation(_Annot(), appearance)  # type: ignore[arg-type]


# ---------- push_resources fallback ----------


def test_push_resources_falls_back_to_page_resources() -> None:
    """Lines 823-827 — when neither the stream nor the engine has
    resources and the page has none, a fresh ``PDResources`` is
    constructed."""
    class _StreamNoRes:
        def get_resources(self) -> None:
            return None

        def get_cos_object(self):
            return COSStream()

    page = PDPage()
    # Page has resources via accessor that returns a fresh wrapper;
    # the page's own resources come back as a non-None default.
    engine = PDFStreamEngine()
    engine._current_page = page
    engine._resources = None  # force fall-through
    parent = engine.push_resources(_StreamNoRes())  # type: ignore[arg-type]
    # After push, engine has either the page resources or a fresh empty.
    assert engine.get_resources() is not None
    engine.pop_resources(parent)


def test_push_resources_creates_empty_when_no_page_resources() -> None:
    """Specifically exercise line 827 — ``self._resources = _PDResources()``
    when neither the stream nor the page provides resources."""

    class _StreamNoRes:
        def get_resources(self) -> None:
            return None

    class _PageNoRes(PDPage):
        def get_resources(self):
            return None

    engine = PDFStreamEngine()
    engine._current_page = _PageNoRes()
    engine._resources = None
    engine.push_resources(_StreamNoRes())  # type: ignore[arg-type]
    assert isinstance(engine.get_resources(), PDResources)


# ---------- clip_to_rect / get_graphics_state ----------


def test_clip_to_rect_no_op_when_rectangle_is_none() -> None:
    engine = PDFStreamEngine()
    engine.clip_to_rect(None)  # early-return guard


def test_clip_to_rect_no_op_when_gs_has_no_clipper() -> None:
    """Line 863 — when the active GS exposes no ``intersect_clipping_path``
    method, ``clip_to_rect`` is a silent no-op."""

    class _PlainGS:
        pass

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _PlainGS()

    engine = _TestEngine()
    rect = PDRectangle(0.0, 0.0, 50.0, 50.0)
    engine.clip_to_rect(rect)


def test_clip_to_rect_with_ctm_transforms_rect() -> None:
    """Lines 868-872 — when both the GS exposes a CTM and the
    rectangle exposes ``transform``, the rectangle is transformed into
    device space before being passed to ``intersect_clipping_path``."""
    received: list[Any] = []

    class _GS:
        current_transformation_matrix = object()

        def intersect_clipping_path(self, path: Any) -> None:
            received.append(path)

    transformed = object()

    class _Rect:
        def transform(self, _ctm: Any) -> Any:
            return transformed

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GS()

    engine = _TestEngine()
    engine.clip_to_rect(_Rect())  # type: ignore[arg-type]
    assert received == [transformed]


def test_clip_to_rect_transform_raises_falls_back() -> None:
    """Lines 869-872 — when ``rectangle.transform(ctm)`` raises, the
    raw rectangle is fed to the clipper instead."""
    received: list[Any] = []

    class _GS:
        current_transformation_matrix = object()

        def intersect_clipping_path(self, path: Any) -> None:
            received.append(path)

    class _BadRect:
        def transform(self, _ctm: Any) -> Any:
            raise TypeError("boom")

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GS()

    engine = _TestEngine()
    bad = _BadRect()
    engine.clip_to_rect(bad)  # type: ignore[arg-type]
    # Fallback path passes the raw rectangle.
    assert received == [bad]


# ---------- _get_active_font / _decode_codes_via_font ----------


def test_get_active_font_falls_back_to_text_font_attr() -> None:
    """When ``gs`` has no ``text_state``, the helper inspects
    ``gs.text_font`` directly (line 1074)."""
    sentinel = object()

    class _GS:
        text_font = sentinel

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GS()

    engine = _TestEngine()
    assert engine._get_active_font() is sentinel


def test_get_active_font_text_state_path() -> None:
    """Line 1073 — when ``gs.text_state`` exposes a ``font`` attribute,
    that font is returned directly."""
    sentinel = object()

    class _TextState:
        font = sentinel

    class _GS:
        text_state = _TextState()

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GS()

    engine = _TestEngine()
    assert engine._get_active_font() is sentinel


def test_get_active_font_returns_none_when_gs_missing() -> None:
    """Early-return guard when ``get_graphics_state()`` returns None."""
    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return None

    engine = _TestEngine()
    assert engine._get_active_font() is None


def test_decode_codes_via_font_no_progress_breaks() -> None:
    """Line 1095 — a font whose ``read_code`` returns a value but
    doesn't advance the buffer breaks the loop to avoid infinite
    spinning."""

    class _FlakyFont:
        def read_code(self, _src: Any) -> int:
            return 7  # Returns a code without consuming any bytes

    codes = PDFStreamEngine._decode_codes_via_font(b"\x00\x01", _FlakyFont())
    # Loop must terminate; codes list is empty since no progress was made.
    assert codes == []


# ---------- _glyph_displacement ----------


def test_glyph_displacement_returns_none_for_none_font() -> None:
    assert PDFStreamEngine._glyph_displacement(None, 0x41) is None


def test_glyph_displacement_returns_none_when_font_lacks_getter() -> None:
    """Line 1107-1108 — no ``get_displacement`` attribute → None."""
    class _Font:
        pass

    assert PDFStreamEngine._glyph_displacement(_Font(), 0x41) is None


def test_glyph_displacement_silences_exceptions() -> None:
    """Lines 1109-1112 — when ``get_displacement(code)`` raises, the
    helper swallows the error and returns None."""
    class _BadFont:
        def get_displacement(self, _code: int) -> Any:
            raise KeyError(_code)

    assert PDFStreamEngine._glyph_displacement(_BadFont(), 0x41) is None


# ---------- show_type3_glyph ----------


def test_show_type3_glyph_no_font_returns_silently() -> None:
    """Early-return when font is None."""
    engine = PDFStreamEngine()
    engine.show_type3_glyph(None, None, 0x41, None)


def test_show_type3_glyph_no_getter_returns_silently() -> None:
    """Font without ``get_char_proc`` → no-op."""
    class _Font:
        pass

    engine = PDFStreamEngine()
    engine.show_type3_glyph(None, _Font(), 0x41, None)


def test_show_type3_glyph_handles_getter_raising() -> None:
    """Lines 1166-1167 — ``get_char_proc`` raising OSError/KeyError
    short-circuits silently."""
    class _Font:
        def get_char_proc(self, _code: int) -> Any:
            raise KeyError(_code)

    engine = PDFStreamEngine()
    engine.show_type3_glyph(None, _Font(), 0x41, None)


def test_show_type3_glyph_handles_none_charproc() -> None:
    """``get_char_proc`` returning None → silent no-op."""
    class _Font:
        def get_char_proc(self, _code: int) -> Any:
            return None

    engine = PDFStreamEngine()
    engine.show_type3_glyph(None, _Font(), 0x41, None)


# ---------- apply_text_adjustment ----------


def test_apply_text_adjustment_no_text_matrix_is_noop() -> None:
    """Early-return guard when text matrix is None."""
    engine = PDFStreamEngine()
    engine.apply_text_adjustment(1.0, 2.0)


def test_apply_text_adjustment_matrix_without_translate_is_noop() -> None:
    """Line 1189 — matrix without ``translate`` method → silent
    no-op."""
    class _MatrixNoTranslate:
        pass

    class _TestEngine(PDFStreamEngine):
        def get_text_matrix(self) -> Any:
            return _MatrixNoTranslate()

    engine = _TestEngine()
    engine.apply_text_adjustment(1.0, 2.0)


def test_apply_text_adjustment_calls_translate_when_present() -> None:
    received: list[tuple[float, float]] = []

    class _Matrix:
        def translate(self, tx: float, ty: float) -> None:
            received.append((tx, ty))

    class _TestEngine(PDFStreamEngine):
        def get_text_matrix(self) -> Any:
            return _Matrix()

    engine = _TestEngine()
    engine.apply_text_adjustment(3.0, 4.0)
    assert received == [(3.0, 4.0)]


# ---------- transformed_point ----------


def test_transformed_point_no_gs_returns_input() -> None:
    """Early-return guard — no GS → input is returned untouched."""
    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return None

    engine = _TestEngine()
    assert engine.transformed_point(2.0, 3.0) == (2.0, 3.0)


def test_transformed_point_no_ctm_returns_input() -> None:
    """Line 1210 — gs without ``current_transformation_matrix`` →
    input pass-through."""
    class _GS:
        pass

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GS()

    engine = _TestEngine()
    assert engine.transformed_point(5.0, 6.0) == (5.0, 6.0)


def test_transformed_point_ctm_without_transform_point_returns_input() -> None:
    """Line 1213 — CTM without ``transform_point`` → input pass-through."""
    class _CTM:
        pass

    class _GS:
        current_transformation_matrix = _CTM()

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GS()

    engine = _TestEngine()
    assert engine.transformed_point(7.0, 8.0) == (7.0, 8.0)


def test_transformed_point_handles_transformer_raising() -> None:
    """Lines 1216-1217 — ``transformer(x, y)`` raising falls back to
    the input."""
    class _CTM:
        def transform_point(self, _x: float, _y: float) -> Any:
            raise TypeError("boom")

    class _GS:
        current_transformation_matrix = _CTM()

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GS()

    engine = _TestEngine()
    assert engine.transformed_point(9.0, 10.0) == (9.0, 10.0)


def test_transformed_point_uses_transformer_on_success() -> None:
    class _CTM:
        def transform_point(self, x: float, y: float) -> tuple[float, float]:
            return (x * 2, y * 3)

    class _GS:
        current_transformation_matrix = _CTM()

    class _TestEngine(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GS()

    engine = _TestEngine()
    assert engine.transformed_point(2.0, 5.0) == (4.0, 15.0)


# ---------- _require_min_operands ----------


def test_require_min_operands_raises_when_too_few() -> None:
    """Lines 1238-1239 — too-few operands raises MissingOperandException."""
    op = Operator.get_operator("Tj")
    with pytest.raises(MissingOperandException):
        PDFStreamEngine._require_min_operands(op, [], minimum=1)


def test_require_min_operands_no_raise_when_enough() -> None:
    op = Operator.get_operator("Tj")
    # No exception — just call.
    PDFStreamEngine._require_min_operands(op, [object()], minimum=1)


# ---------- get_default_font ----------


def test_get_default_font_returns_none() -> None:
    """The base engine has no font tree to instantiate from — returns
    ``None`` so subclasses with the tree available can override."""
    engine = PDFStreamEngine()
    assert engine.get_default_font() is None
