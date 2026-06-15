from __future__ import annotations

import io
from typing import IO, Any, ClassVar

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    OperatorProcessor,
    PDContentStream,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import (
    BeginText,
    EndText,
    MoveText,
    MoveTextSetLeading,
    SetFontAndSize,
    SetMatrix,
    ShowText,
    ShowTextAdjusted,
    ShowTextLine,
    ShowTextLineAndSpace,
)
from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.io.random_access_read import RandomAccessRead
from pypdfbox.io.random_access_read_buffer import RandomAccessReadBuffer
from pypdfbox.pdmodel import PDPage, PDRectangle, PDResources


class _Recorder(OperatorProcessor):
    """Records every dispatch so tests can assert order + operands."""

    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.calls: list[tuple[str, list[COSBase]]] = []

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self.calls.append((operator.get_name(), list(operands)))

    def get_name(self) -> str:
        return self._name


class _RecordingEngine(PDFStreamEngine):
    """Engine subclass that captures every text-hook invocation in order
    so tests can assert the parse → dispatch → engine pipeline end-to-
    end without poking at private operator internals."""

    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, tuple[Any, ...]]] = []
        self.unsupported: list[tuple[str, list[COSBase]]] = []

    def begin_text(self) -> None:
        self.events.append(("begin_text", ()))

    def end_text(self) -> None:
        self.events.append(("end_text", ()))

    def set_font(self, font_name: COSName, font_size: float) -> None:
        self.events.append(("set_font", (font_name, font_size)))

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        self.events.append(("set_text_matrix", (matrix,)))

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        self.events.append(("set_text_line_matrix", (matrix,)))

    def move_text_position(self, tx: float, ty: float) -> None:
        self.events.append(("move_text_position", (tx, ty)))

    def show_text_string(self, text: bytes) -> None:
        self.events.append(("show_text_string", (text,)))

    def show_text_strings(self, array: COSArray) -> None:
        self.events.append(("show_text_strings", (array,)))

    def set_text_leading(self, leading: float) -> None:
        self.events.append(("set_text_leading", (leading,)))

    def unsupported_operator(
        self, operator: Operator, operands: list[COSBase]
    ) -> None:
        self.unsupported.append((operator.get_name(), list(operands)))


def _register_all_text_ops(engine: PDFStreamEngine) -> None:
    for cls in (
        BeginText,
        EndText,
        SetFontAndSize,
        SetMatrix,
        MoveText,
        MoveTextSetLeading,
        ShowText,
        ShowTextAdjusted,
        ShowTextLine,
        ShowTextLineAndSpace,
    ):
        engine.add_operator(cls())


# ---------- registration ----------


def test_add_operator_registers_by_name_and_binds_context() -> None:
    engine = PDFStreamEngine()
    proc = _Recorder("Tj")
    engine.add_operator(proc)
    assert engine.get_operators()["Tj"] is proc
    assert proc.get_context() is engine


def test_register_operator_processor_uses_explicit_name() -> None:
    engine = PDFStreamEngine()
    proc = _Recorder("Tj")
    engine.register_operator_processor("alias", proc)
    assert engine.get_operators()["alias"] is proc
    assert "Tj" not in engine.get_operators()
    assert proc.get_context() is engine


# ---------- dispatch ----------


def test_process_operator_dispatches_to_registered_processor() -> None:
    engine = PDFStreamEngine()
    proc = _Recorder("Tj")
    engine.add_operator(proc)
    op = Operator.get_operator("Tj")
    engine.process_operator(op, [COSString(b"hi")])
    assert len(proc.calls) == 1
    assert proc.calls[0][0] == "Tj"


def test_process_operator_accepts_str_form() -> None:
    engine = PDFStreamEngine()
    proc = _Recorder("Tj")
    engine.add_operator(proc)
    engine.process_operator("Tj", [])
    assert proc.calls and proc.calls[0][0] == "Tj"


def test_process_operator_none_operands_treated_as_empty() -> None:
    engine = PDFStreamEngine()
    proc = _Recorder("BT")
    engine.add_operator(proc)
    engine.process_operator("BT", None)
    assert proc.calls and proc.calls[0][1] == []


def test_unsupported_operator_invoked_when_no_processor() -> None:
    engine = _RecordingEngine()
    engine.process_operator("ZZ", [COSInteger.get(1)])
    assert engine.unsupported == [("ZZ", [COSInteger.get(1)])]


def test_unsupported_operator_default_is_no_op() -> None:
    engine = PDFStreamEngine()
    # Should not raise.
    engine.process_operator("ZZ", [])


def test_operator_exception_demotes_missing_operand() -> None:
    engine = PDFStreamEngine()

    class _BadShow(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            raise MissingOperandException(operator, operands)

        def get_name(self) -> str:
            return "Tj"

    engine.add_operator(_BadShow())
    # Should swallow rather than raise, mirroring upstream's triage.
    engine.process_operator("Tj", [])


def test_operator_exception_reraises_unknown_io_error() -> None:
    engine = PDFStreamEngine()

    class _Boom(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            raise OSError("boom")

        def get_name(self) -> str:
            return "Tj"

    engine.add_operator(_Boom())
    with pytest.raises(OSError, match="boom"):
        engine.process_operator("Tj", [])


def test_operator_exception_demotes_do_failures() -> None:
    engine = PDFStreamEngine()

    class _BadDo(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            raise OSError("xobject missing")

        def get_name(self) -> str:
            return "Do"

    engine.add_operator(_BadDo())
    # ``Do`` failures are demoted to a warn — should not raise.
    engine.process_operator("Do", [])


# ---------- end-to-end parse → dispatch ----------


class _BytesContentStream(PDContentStream):
    """Tiny PDContentStream wrapping raw bytes for round-trip tests."""

    def __init__(self, data: bytes) -> None:
        self._data = data

    def get_contents(self) -> IO[bytes]:
        return io.BytesIO(self._data)

    def get_contents_for_random_access(self) -> RandomAccessRead:
        return RandomAccessReadBuffer(self._data)

    def get_resources(self) -> PDResources | None:
        return PDResources()

    def get_bbox(self) -> PDRectangle:
        return PDRectangle(0.0, 0.0, 612.0, 792.0)

    def get_matrix(self) -> Any:
        return None


def test_round_trip_minimal_text_object() -> None:
    """The headline pipeline test: build a content stream, dispatch
    through the engine with all 9 ops registered, assert that each
    handler was invoked in source order with the right operands."""
    engine = _RecordingEngine()
    _register_all_text_ops(engine)

    stream = _BytesContentStream(b"BT /F1 12 Tf 100 200 Td (Hello) Tj ET")
    engine.process_stream(stream)

    # Filter to the top-level engine notifications. ``BT`` fires
    # set_text_matrix + set_text_line_matrix + begin_text; ``Tf`` fires
    # set_font; ``Td`` fires move_text_position; ``Tj`` fires
    # show_text_string; ``ET`` fires set_text_line_matrix(None) +
    # set_text_matrix(None) + end_text (upstream clear order, wave 1535).
    sequence = [name for name, _ in engine.events]
    assert sequence == [
        "set_text_matrix",
        "set_text_line_matrix",
        "begin_text",
        "set_font",
        "move_text_position",
        "show_text_string",
        "set_text_line_matrix",
        "set_text_matrix",
        "end_text",
    ]
    # Spot-check operands for the load-bearing handlers.
    by_name = {name: args for name, args in engine.events}
    assert by_name["set_font"] == (COSName.get_pdf_name("F1"), 12.0)
    assert by_name["move_text_position"] == (100.0, 200.0)
    assert by_name["show_text_string"] == (b"Hello",)


def test_round_trip_show_text_adjusted() -> None:
    engine = _RecordingEngine()
    _register_all_text_ops(engine)
    stream = _BytesContentStream(b"BT [(He) -120 (llo)] TJ ET")
    engine.process_stream(stream)
    tj_events = [a for n, a in engine.events if n == "show_text_strings"]
    assert len(tj_events) == 1
    array = tj_events[0][0]
    assert isinstance(array, COSArray)
    assert array.size() == 3


def test_round_trip_show_text_line_decomposes() -> None:
    """``'`` should re-enter the engine via processOperator, surfacing
    a NEXT_LINE attempt (no handler in cluster #2 → unsupported) and a
    Tj show_text_string."""
    engine = _RecordingEngine()
    _register_all_text_ops(engine)
    stream = _BytesContentStream(b"BT (Hi) ' ET")
    engine.process_stream(stream)
    # NEXT_LINE has no registered processor in cluster #2.
    assert ("T*", []) in engine.unsupported
    # And the Tj fires.
    assert ("show_text_string", (b"Hi",)) in engine.events


def test_round_trip_show_text_line_and_space_decomposes() -> None:
    engine = _RecordingEngine()
    _register_all_text_ops(engine)
    stream = _BytesContentStream(b"BT 1 2 (Hi) \" ET")
    engine.process_stream(stream)
    unsupported_names = [name for name, _ in engine.unsupported]
    # ``"`` decomposes to Tw, Tc, ' — none of which we registered as
    # individual handlers (Tw/Tc/T*). So all three fall through to
    # unsupported_operator, while the inner Tj from ' does fire.
    assert "Tw" in unsupported_names
    assert "Tc" in unsupported_names
    assert ("show_text_string", (b"Hi",)) in engine.events


def test_process_page_walks_contents() -> None:
    engine = _RecordingEngine()
    _register_all_text_ops(engine)
    page = PDPage()
    # Attach a tiny Contents stream.
    from pypdfbox.cos import COSStream

    cs = COSStream()
    with cs.create_raw_output_stream() as out:
        out.write(b"BT /F1 12 Tf (X) Tj ET")
    page.set_contents(cs)

    engine.process_page(page)
    sequence = [name for name, _ in engine.events]
    assert "begin_text" in sequence
    assert ("show_text_string", (b"X",)) in engine.events
    assert sequence[-1] == "end_text"


def test_process_page_no_contents_is_noop() -> None:
    engine = _RecordingEngine()
    _register_all_text_ops(engine)
    engine.process_page(PDPage())
    assert engine.events == []


# ---------- get_operator / get_operators ----------


def test_get_operator_returns_registered_processor() -> None:
    engine = PDFStreamEngine()
    proc = _Recorder("Tj")
    engine.add_operator(proc)
    assert engine.get_operator("Tj") is proc


def test_get_operator_returns_none_for_unknown() -> None:
    engine = PDFStreamEngine()
    assert engine.get_operator("ZZ") is None


# ---------- graphics-state surface ----------


def test_get_graphics_state_default_is_none() -> None:
    """Base engine reports no current graphics-state frame."""
    engine = PDFStreamEngine()
    assert engine.get_graphics_state() is None
    assert engine.get_graphics_stack_size() == 0


def test_save_restore_graphics_state_base_is_noop() -> None:
    """Base ``save`` / ``restore`` are observable no-ops — they don't
    push/pop the stack themselves; only subclasses do."""
    engine = PDFStreamEngine()
    engine.save_graphics_state()
    engine.save_graphics_state()
    assert engine.get_graphics_stack_size() == 0
    engine.restore_graphics_state()
    assert engine.get_graphics_stack_size() == 0


def test_subclass_can_drive_graphics_state_stack() -> None:
    """Subclasses with a real graphics state push frames into the
    inherited ``_graphics_stack`` and override the hooks; the base
    accessor returns the top of the stack as-is."""

    class _GfxEngine(PDFStreamEngine):
        def save_graphics_state(self) -> None:
            top = self.get_graphics_state()
            self._graphics_stack.append({"depth": (top or {}).get("depth", 0) + 1})

        def restore_graphics_state(self) -> None:
            self._graphics_stack.pop()

    engine = _GfxEngine()
    engine.save_graphics_state()
    engine.save_graphics_state()
    assert engine.get_graphics_stack_size() == 2
    assert engine.get_graphics_state() == {"depth": 2}
    engine.restore_graphics_state()
    assert engine.get_graphics_state() == {"depth": 1}


def test_transform_default_is_noop() -> None:
    """Base ``transform`` is a no-op — the rendering subclass overrides
    to multiply the matrix into the active CTM."""
    engine = PDFStreamEngine()
    # Should not raise and should not affect any observable state.
    engine.transform([1, 0, 0, 1, 10, 20])
    assert engine.get_graphics_state() is None


# ---------- text-matrix accessors ----------


def test_text_matrix_object_round_trip() -> None:
    engine = PDFStreamEngine()
    assert engine.get_text_matrix() is None
    sentinel = object()
    engine.set_text_matrix_object(sentinel)
    assert engine.get_text_matrix() is sentinel
    engine.set_text_matrix_object(None)
    assert engine.get_text_matrix() is None


def test_text_line_matrix_object_round_trip() -> None:
    engine = PDFStreamEngine()
    assert engine.get_text_line_matrix() is None
    sentinel = object()
    engine.set_text_line_matrix_object(sentinel)
    assert engine.get_text_line_matrix() is sentinel


# ---------- show_text / show_font_glyph / show_glyph hooks ----------


class _GlyphRecorder(PDFStreamEngine):
    """Subclass that records each ``show_font_glyph`` / ``show_glyph``
    invocation so tests can assert the per-byte dispatch path."""

    glyphs: ClassVar[list[tuple[int, Any]]]

    def __init__(self) -> None:
        super().__init__()
        self.font_glyphs: list[tuple[Any, Any, int, Any]] = []
        self.glyphs_called: list[tuple[Any, Any, int, Any]] = []

    def show_font_glyph(
        self, text_rendering_matrix: Any, font: Any, code: int, displacement: Any
    ) -> None:
        self.font_glyphs.append((text_rendering_matrix, font, code, displacement))
        super().show_font_glyph(text_rendering_matrix, font, code, displacement)

    def show_glyph(
        self, text_rendering_matrix: Any, font: Any, code: int, displacement: Any
    ) -> None:
        self.glyphs_called.append((text_rendering_matrix, font, code, displacement))


def test_show_text_dispatches_one_show_font_glyph_per_byte_when_no_font() -> None:
    """No active font ⇒ fall-back per-byte dispatch (one code per byte)."""
    engine = _GlyphRecorder()
    engine.show_text(b"AB")
    codes = [c for _, _, c, _ in engine.font_glyphs]
    assert codes == [ord("A"), ord("B")]
    # show_font_glyph base implementation forwards to show_glyph.
    forwarded = [c for _, _, c, _ in engine.glyphs_called]
    assert forwarded == codes


def test_show_text_uses_font_read_code_when_available() -> None:
    """When a font with ``read_code`` is on the graphics state, decode
    via that — proves multi-byte fonts would be honoured."""

    class _TwoByteFont:
        def read_code(self, src: Any) -> int | None:
            chunk = src.read(2)
            if len(chunk) < 2:
                return None
            return (chunk[0] << 8) | chunk[1]

    class _GS:
        text_font = _TwoByteFont()

    engine = _GlyphRecorder()
    engine._graphics_stack.append(_GS())
    engine.show_text(b"\x00\x41\x00\x42\x00\x43")
    codes = [c for _, _, c, _ in engine.font_glyphs]
    assert codes == [0x41, 0x42, 0x43]


def test_show_text_empty_bytes_dispatches_nothing() -> None:
    engine = _GlyphRecorder()
    engine.show_text(b"")
    assert engine.font_glyphs == []
    assert engine.glyphs_called == []


def test_show_font_glyph_default_forwards_to_show_glyph() -> None:
    """The base ``show_font_glyph`` implementation defers to
    ``show_glyph`` so a subclass can override either layer."""

    class _OnlyShowGlyph(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.codes: list[int] = []

        def show_glyph(
            self,
            text_rendering_matrix: Any,
            font: Any,
            code: int,
            displacement: Any,
        ) -> None:
            self.codes.append(code)

    engine = _OnlyShowGlyph()
    engine.show_font_glyph(None, None, 0x41, None)
    engine.show_font_glyph(None, None, 0x42, None)
    assert engine.codes == [0x41, 0x42]


# ---------- process_child_stream ----------


def test_process_child_stream_dispatches_through_engine() -> None:
    """A nested content stream walks through the same dispatch
    pipeline; the operator processors see operators from the child."""
    engine = _RecordingEngine()
    _register_all_text_ops(engine)
    page = PDPage()
    page.set_resources(PDResources())
    child = _BytesContentStream(b"BT (Inner) Tj ET")

    engine.process_child_stream(child, page)

    assert ("show_text_string", (b"Inner",)) in engine.events


def test_process_child_stream_sets_current_page_for_duration() -> None:
    """``get_current_page`` reflects ``page`` while the child stream
    runs and restores after."""

    class _PageProbe(OperatorProcessor):
        def __init__(self) -> None:
            super().__init__()
            self.seen: list[Any] = []

        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            self.seen.append(self.get_context().get_current_page())

        def get_name(self) -> str:
            return "Tj"

    engine = PDFStreamEngine()
    probe = _PageProbe()
    engine.add_operator(probe)
    page = PDPage()
    page.set_resources(PDResources())
    child = _BytesContentStream(b"(X) Tj")
    assert engine.get_current_page() is None
    engine.process_child_stream(child, page)
    assert probe.seen == [page]
    # After child stream, the engine resets to the prior context.
    assert engine.get_current_page() is None
    assert engine.is_processing_page() is False


def test_process_child_stream_does_not_increment_level() -> None:
    """A nested stream does NOT bump ``get_level`` — upstream manages the
    recursion level exclusively from ``DrawObject`` (the ``Do`` form-XObject
    handler), so ``processStream`` leaves it untouched (wave 1472)."""

    class _LevelProbe(OperatorProcessor):
        def __init__(self) -> None:
            super().__init__()
            self.levels: list[int] = []

        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            self.levels.append(self.get_context().get_level())

        def get_name(self) -> str:
            return "Tj"

    engine = PDFStreamEngine()
    probe = _LevelProbe()
    engine.add_operator(probe)
    child = _BytesContentStream(b"(X) Tj")
    engine.process_child_stream(child, None)
    assert probe.levels == [0]
    assert engine.get_level() == 0


def test_level_accessors_round_trip() -> None:
    """Public level helpers mirror upstream increaseLevel/decreaseLevel."""
    engine = PDFStreamEngine()
    assert engine.get_level() == 0
    engine.increase_level()
    engine.increase_level()
    assert engine.get_level() == 2
    engine.decrease_level()
    assert engine.get_level() == 1
    engine.decrease_level()
    assert engine.get_level() == 0


def test_decrease_level_below_zero_logs_and_clamps(caplog: pytest.LogCaptureFixture) -> None:
    engine = PDFStreamEngine()

    with caplog.at_level("ERROR", logger="pypdfbox.contentstream.pdf_stream_engine"):
        engine.decrease_level()

    assert engine.get_level() == 0
    assert "level is below 0" in caplog.text


def test_process_stream_does_not_touch_level_helpers() -> None:
    """``process_stream`` must NOT call ``increase_level`` / ``decrease_level``.

    Upstream's private ``processStream`` leaves the recursion level alone —
    only ``DrawObject`` (the ``Do`` form-XObject handler) bumps it, so the
    ``getLevel() > 50`` cap counts form-XObject ``Do`` recursion depth and
    nothing else (wave 1472).
    """

    class _LevelEngine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.transitions: list[tuple[str, int]] = []

        def increase_level(self) -> None:
            super().increase_level()
            self.transitions.append(("increase", self.get_level()))

        def decrease_level(self) -> None:
            before = self.get_level()
            super().decrease_level()
            self.transitions.append(("decrease", before))

    engine = _LevelEngine()
    engine.process_stream(_BytesContentStream(b""))

    assert engine.transitions == []
    assert engine.get_level() == 0


def test_process_child_stream_without_page_preserves_outer_context() -> None:
    """``page=None`` runs the child without disturbing the outer
    current-page state. (This matches our use for annotation appearances
    that don't override the page reference.)"""
    engine = PDFStreamEngine()
    page = PDPage()
    page.set_resources(PDResources())
    cs = _BytesContentStream(b"(A) Tj")
    # Simulate already being inside process_page.
    engine._current_page = page
    engine._is_processing_page = True
    try:
        engine.process_child_stream(cs, None)
    finally:
        engine._current_page = None
        engine._is_processing_page = False
    # The outer state was preserved across the child run.
    assert engine.get_current_page() is None
    assert engine.is_processing_page() is False


# ---------- save_graphics_stack / restore_graphics_stack ----------


def test_save_graphics_stack_returns_previous_and_seeds_one_frame() -> None:
    """``save_graphics_stack`` returns the prior list and replaces the
    live stack with a single-frame stack carrying a copy of the prior
    top — mirrors upstream's snapshot/seed contract."""
    engine = PDFStreamEngine()
    frame_a = {"depth": 1}
    frame_b = {"depth": 2}
    engine._graphics_stack.append(frame_a)
    engine._graphics_stack.append(frame_b)

    snapshot = engine.save_graphics_stack()

    # The returned snapshot is the original list reference.
    assert snapshot is not engine._graphics_stack
    assert snapshot == [frame_a, frame_b]
    # The new live stack has exactly one frame, equal to the prior top
    # but a copy (so the inner stream's mutations don't bleed back).
    assert engine.get_graphics_stack_size() == 1
    assert engine.get_graphics_state() == frame_b
    assert engine.get_graphics_state() is not frame_b


def test_save_graphics_stack_when_empty_yields_empty_seed() -> None:
    """Saving an empty stack returns an empty snapshot and leaves the
    live stack empty (no top frame to seed from)."""
    engine = PDFStreamEngine()
    snapshot = engine.save_graphics_stack()
    assert snapshot == []
    assert engine.get_graphics_stack_size() == 0


def test_save_graphics_stack_uncopyable_top_falls_back_to_reference() -> None:
    """Frames that aren't ``copy.copy``-able still seed the new stack —
    we fall back to the original reference rather than dropping the
    frame entirely."""

    class _Uncopyable:
        def __copy__(self) -> _Uncopyable:
            raise TypeError("intentionally uncopyable")

    engine = PDFStreamEngine()
    frame = _Uncopyable()
    engine._graphics_stack.append(frame)

    snapshot = engine.save_graphics_stack()

    assert snapshot == [frame]
    assert engine.get_graphics_stack_size() == 1
    # Falling back keeps the same reference — verifies we don't lose
    # the frame when ``copy.copy`` can't clone it.
    assert engine.get_graphics_state() is frame


def test_restore_graphics_stack_replaces_live_stack_wholesale() -> None:
    """``restore_graphics_stack`` swaps the live stack for the supplied
    snapshot — verifying the snapshot/restore round-trip works end-to-
    end."""
    engine = PDFStreamEngine()
    engine._graphics_stack.append({"depth": 1})
    engine._graphics_stack.append({"depth": 2})

    snapshot = engine.save_graphics_stack()

    # Mutate the inner stack; the snapshot is unaffected.
    engine._graphics_stack.append({"inner": True})
    assert engine.get_graphics_stack_size() == 2

    engine.restore_graphics_stack(snapshot)

    assert engine._graphics_stack is snapshot
    assert engine.get_graphics_stack_size() == 2
    assert engine.get_graphics_state() == {"depth": 2}


# ---------- transform_width ----------


def test_transform_width_default_is_identity() -> None:
    """Base engine has no concrete CTM and returns the width as-is —
    cluster #2 contract; the rendering subclass overrides."""
    engine = PDFStreamEngine()
    assert engine.transform_width(1.5) == 1.5
    assert engine.transform_width(0.0) == 0.0


def test_transform_width_returns_float_for_int_input() -> None:
    """Even with an integer input we return a float — matches upstream's
    ``protected float transformWidth(float)`` return type."""
    engine = PDFStreamEngine()
    out = engine.transform_width(3)
    assert isinstance(out, float)
    assert out == 3.0


def test_transform_width_override_routed_through() -> None:
    """A subclass that overrides ``transform_width`` controls the
    returned scalar — verifies the hook is overridable."""

    class _Scaled(PDFStreamEngine):
        def transform_width(self, width: float) -> float:
            return width * 2.0

    engine = _Scaled()
    assert engine.transform_width(2.5) == 5.0


# ---------- set_line_dash_pattern ----------


def test_set_line_dash_pattern_base_is_noop() -> None:
    """Base ``set_line_dash_pattern`` accepts the ``d`` operator's
    operands and silently swallows them — cluster #2 has no
    ``PDLineDashPattern`` to materialise."""
    engine = PDFStreamEngine()
    arr = COSArray()
    arr.add(COSInteger.get(3))
    arr.add(COSInteger.get(2))
    # Should not raise; assertion is just that we get there.
    engine.set_line_dash_pattern(arr, 0)
    engine.set_line_dash_pattern(COSArray(), 5)


def test_set_line_dash_pattern_override_observes_operands() -> None:
    """A subclass that overrides ``set_line_dash_pattern`` receives the
    raw ``COSArray`` + phase exactly as upstream's ``setLineDashPattern``
    handler passes them."""
    captured: list[tuple[COSArray, int]] = []

    class _Probe(PDFStreamEngine):
        def set_line_dash_pattern(self, array: COSArray, phase: int) -> None:
            captured.append((array, phase))

    engine = _Probe()
    arr = COSArray()
    arr.add(COSInteger.get(4))
    engine.set_line_dash_pattern(arr, 7)

    assert captured == [(arr, 7)]


# ---------- show_form / show_transparency_group ----------


def _make_form_xobject(body: bytes) -> Any:
    """Construct a minimal ``PDFormXObject`` whose underlying COSStream
    carries the supplied raw bytes — used by the show_form tests below."""
    from pypdfbox.cos import COSStream  # noqa: PLC0415
    from pypdfbox.pdmodel.graphics.form.pd_form_x_object import (  # noqa: PLC0415
        PDFormXObject,
    )

    cos = COSStream()
    if body:
        cos.set_raw_data(body)
    return PDFormXObject(cos)


def test_show_form_raises_without_current_page() -> None:
    """No current page ⇒ raise ``RuntimeError`` (upstream:
    ``IllegalStateException``) pointing at ``process_child_stream``."""
    engine = PDFStreamEngine()
    form = _make_form_xobject(b"")
    with pytest.raises(RuntimeError, match="process_child_stream"):
        engine.show_form(form)


def test_show_form_skips_empty_stream() -> None:
    """Empty form ⇒ silent skip; the engine never enters the parser
    loop. Probe by registering an operator that would crash if called."""

    class _Boom(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            raise AssertionError("operator dispatch must not happen")

        def get_name(self) -> str:
            return "Tj"

    engine = PDFStreamEngine()
    engine.add_operator(_Boom())
    engine._current_page = PDPage()
    engine._is_processing_page = True
    try:
        # Empty body — show_form must early-return.
        form = _make_form_xobject(b"")
        engine.show_form(form)  # would AssertionError if the parser ran
    finally:
        engine._current_page = None
        engine._is_processing_page = False


def test_show_form_dispatches_non_empty_body_through_engine() -> None:
    """A non-empty form body drives the operator dispatch loop just like
    ``process_stream`` would."""

    class _Probe(OperatorProcessor):
        def __init__(self) -> None:
            super().__init__()
            self.calls: list[list[COSBase]] = []

        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            self.calls.append(list(operands))

        def get_name(self) -> str:
            return "Tj"

    engine = PDFStreamEngine()
    probe = _Probe()
    engine.add_operator(probe)
    engine._current_page = PDPage()
    engine._is_processing_page = True
    try:
        form = _make_form_xobject(b"(InForm) Tj")
        engine.show_form(form)
    finally:
        engine._current_page = None
        engine._is_processing_page = False

    assert len(probe.calls) == 1


def test_show_form_does_not_increment_level_through_process_stream() -> None:
    """``show_form`` routes through ``process_stream`` — which does NOT
    touch the recursion level. Only ``DrawObject`` bumps the level, so a
    plain ``show_form`` runs the inner operators at the same level (wave
    1472)."""

    class _Probe(OperatorProcessor):
        def __init__(self) -> None:
            super().__init__()
            self.levels: list[int] = []

        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            self.levels.append(self.get_context().get_level())

        def get_name(self) -> str:
            return "Tj"

    engine = PDFStreamEngine()
    probe = _Probe()
    engine.add_operator(probe)
    engine._current_page = PDPage()
    engine._is_processing_page = True
    try:
        form = _make_form_xobject(b"(X) Tj")
        engine.show_form(form)
    finally:
        engine._current_page = None
        engine._is_processing_page = False

    assert probe.levels == [0]
    assert engine.get_level() == 0


def test_show_transparency_group_routes_through_process_stream() -> None:
    """Cluster #2 alias for transparency-group dispatch — runs the
    operators just like ``process_stream`` does. Mirrors upstream's
    ``showTransparencyGroup`` -> ``processTransparencyGroup`` chain
    which requires a current page."""

    class _Probe(OperatorProcessor):
        def __init__(self) -> None:
            super().__init__()
            self.calls: int = 0

        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            self.calls += 1

        def get_name(self) -> str:
            return "Tj"

    from pypdfbox.cos import COSStream  # noqa: PLC0415
    from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (  # noqa: PLC0415
        PDTransparencyGroup,
    )

    engine = PDFStreamEngine()
    probe = _Probe()
    engine.add_operator(probe)
    engine._current_page = PDPage()
    engine._is_processing_page = True

    cos = COSStream()
    cos.set_raw_data(b"(Tx) Tj")
    group = PDTransparencyGroup(cos)
    try:
        engine.show_transparency_group(group)
    finally:
        engine._current_page = None
        engine._is_processing_page = False

    assert probe.calls == 1


def test_show_transparency_group_raises_without_current_page() -> None:
    """No current page ⇒ ``RuntimeError`` (upstream:
    ``IllegalStateException``) — matches the same fence
    ``show_form`` / ``process_transparency_group`` use."""
    from pypdfbox.cos import COSStream  # noqa: PLC0415
    from pypdfbox.pdmodel.graphics.form.pd_transparency_group import (  # noqa: PLC0415
        PDTransparencyGroup,
    )

    engine = PDFStreamEngine()
    cos = COSStream()
    cos.set_raw_data(b"(X) Tj")
    group = PDTransparencyGroup(cos)
    with pytest.raises(RuntimeError, match="process_child_stream"):
        engine.show_transparency_group(group)


# ---------- init_page / push_resources / pop_resources ----------


def test_init_page_clears_graphics_stack_and_seeds_resources() -> None:
    """``init_page`` mirrors upstream's ``initPage(PDPage)``: sets the
    current page, clears the graphics stack, and seeds resources."""
    engine = PDFStreamEngine()
    # Pre-populate with stale state to verify init_page wipes it.
    engine._graphics_stack.append({"depth": 9})
    page = PDPage()
    res = PDResources()
    page.set_resources(res)

    engine.init_page(page)

    assert engine.get_current_page() is page
    assert engine.get_graphics_stack_size() == 0
    # PDPage.get_resources() builds a fresh wrapper around the same COS
    # dict each call, so compare via the underlying COS dict.
    seeded = engine.get_resources()
    assert seeded is not None
    assert seeded.get_cos_object() is res.get_cos_object()


def test_init_page_rejects_none_page() -> None:
    """``init_page(None)`` raises ``ValueError`` — upstream throws
    ``IllegalArgumentException`` for the same input."""
    engine = PDFStreamEngine()
    with pytest.raises(ValueError, match="cannot be null"):
        engine.init_page(None)  # type: ignore[arg-type]


def test_push_resources_replaces_current_and_returns_parent() -> None:
    """``push_resources`` returns the previously active resources frame
    and swaps in the stream's own."""

    class _StreamWithResources(_BytesContentStream):
        def __init__(self, body: bytes, res: PDResources) -> None:
            super().__init__(body)
            self._res = res

        def get_resources(self) -> PDResources | None:
            return self._res

    engine = PDFStreamEngine()
    parent_res = PDResources()
    engine._resources = parent_res
    child_res = PDResources()
    stream = _StreamWithResources(b"", child_res)

    returned = engine.push_resources(stream)

    assert returned is parent_res
    assert engine.get_resources() is child_res


def test_push_resources_inherits_parent_when_stream_has_none() -> None:
    """A stream with no resources falls through to the parent resources
    (PDFBOX-1359 semantics)."""
    engine = PDFStreamEngine()
    parent_res = PDResources()
    engine._resources = parent_res
    stream = _BytesContentStream(b"")  # default get_resources() returns a fresh
    # We want the no-resources path: override.
    stream.get_resources = lambda: None  # type: ignore[method-assign]

    returned = engine.push_resources(stream)

    assert returned is parent_res
    assert engine.get_resources() is parent_res


def test_push_resources_falls_back_to_page_when_no_parent() -> None:
    """No parent resources, no stream resources ⇒ fall back to the
    page's resources, or a fresh empty :class:`PDResources` when the
    page has none."""
    engine = PDFStreamEngine()
    page = PDPage()
    page_res = PDResources()
    page.set_resources(page_res)
    engine._current_page = page

    stream = _BytesContentStream(b"")
    stream.get_resources = lambda: None  # type: ignore[method-assign]

    returned = engine.push_resources(stream)

    assert returned is None
    seeded = engine.get_resources()
    assert seeded is not None
    assert seeded.get_cos_object() is page_res.get_cos_object()


def test_pop_resources_restores_parent_frame() -> None:
    engine = PDFStreamEngine()
    parent_res = PDResources()
    engine._resources = PDResources()  # current frame
    engine.pop_resources(parent_res)
    assert engine.get_resources() is parent_res


# ---------- process_stream_operators ----------


def test_process_stream_operators_drives_dispatch() -> None:
    """Direct call to ``process_stream_operators`` runs the operators
    without entering the wrapping ``process_stream`` resource fence —
    matches upstream's ``processStreamOperators`` private surface."""
    engine = _RecordingEngine()
    _register_all_text_ops(engine)
    stream = _BytesContentStream(b"BT (Hello) Tj ET")
    engine.process_stream_operators(stream)
    assert ("show_text_string", (b"Hello",)) in engine.events


# ---------- get_appearance / show_annotation ----------


def test_get_appearance_returns_normal_appearance_stream() -> None:
    """``get_appearance(annotation)`` defaults to the annotation's
    normal appearance — matches upstream's contract."""

    sentinel = object()

    class _Annot:
        def get_normal_appearance_stream(self) -> Any:
            return sentinel

    engine = PDFStreamEngine()
    assert engine.get_appearance(_Annot()) is sentinel


def test_get_appearance_returns_none_when_annotation_lacks_method() -> None:
    engine = PDFStreamEngine()
    assert engine.get_appearance(object()) is None  # type: ignore[arg-type]


def test_show_annotation_no_appearance_is_silent_skip() -> None:
    """No appearance stream ⇒ no dispatch, no exception. Mirrors
    upstream's ``showAnnotation`` which skips when ``getAppearance``
    returns null."""

    class _Annot:
        def get_normal_appearance_stream(self) -> Any:
            return None

    engine = PDFStreamEngine()
    engine.show_annotation(_Annot())  # type: ignore[arg-type]


def test_process_annotation_skips_zero_sized_rect() -> None:
    """Annotations with a zero rect are skipped — PDFBOX-4783."""
    calls: list[str] = []

    class _Rect:
        def get_width(self) -> float:
            return 0.0

        def get_height(self) -> float:
            return 100.0

    class _Appearance:
        def get_bbox(self) -> Any:
            return _Rect()

        def get_resources(self) -> PDResources | None:
            return None

    class _Annot:
        def get_rectangle(self) -> Any:
            return _Rect()

    class _Engine(PDFStreamEngine):
        def process_stream_operators(
            self, content_stream: PDContentStream
        ) -> None:
            calls.append("dispatched")

    engine = _Engine()
    engine.process_annotation(_Annot(), _Appearance())  # type: ignore[arg-type]
    assert calls == []


# ---------- apply_text_adjustment ----------


def test_apply_text_adjustment_translates_when_matrix_supports_it() -> None:
    """``apply_text_adjustment`` delegates to the stored text matrix's
    ``translate`` if available — matches upstream's
    ``getTextMatrix().translate(tx, ty)``."""
    captured: list[tuple[float, float]] = []

    class _Mat:
        def translate(self, tx: float, ty: float) -> None:
            captured.append((tx, ty))

    engine = PDFStreamEngine()
    engine.set_text_matrix_object(_Mat())
    engine.apply_text_adjustment(1.5, 2.0)
    assert captured == [(1.5, 2.0)]


def test_apply_text_adjustment_no_op_without_matrix() -> None:
    engine = PDFStreamEngine()
    # Should not raise — silently no-ops.
    engine.apply_text_adjustment(1.0, 2.0)


# ---------- transformed_point ----------


def test_transformed_point_default_is_identity() -> None:
    engine = PDFStreamEngine()
    assert engine.transformed_point(5.0, 7.0) == (5.0, 7.0)


def test_transformed_point_uses_ctm_when_available() -> None:
    class _CTM:
        def transform_point(self, x: float, y: float) -> tuple[float, float]:
            return (x + 10, y + 20)

    class _GS:
        current_transformation_matrix = _CTM()

    engine = PDFStreamEngine()
    engine._graphics_stack.append(_GS())
    assert engine.transformed_point(1.0, 2.0) == (11.0, 22.0)


# ---------- get_default_font ----------


def test_get_default_font_default_is_none() -> None:
    """Cluster #2 base has no font tree; the default font helper
    returns ``None``. Subclasses with the font tree override."""
    engine = PDFStreamEngine()
    assert engine.get_default_font() is None


# ---------- show_type3_glyph ----------


def test_show_type3_glyph_drives_process_type3_stream() -> None:
    """``show_type3_glyph`` looks up the glyph's char-proc and re-enters
    dispatch via :meth:`process_type3_stream`."""
    captured: list[Any] = []

    class _CharProc:
        pass

    cp = _CharProc()

    class _Type3Font:
        def get_char_proc(self, code: int) -> Any:
            return cp if code == 65 else None

    class _Engine(PDFStreamEngine):
        def process_type3_stream(
            self, charproc: PDContentStream, text_matrix: Any | None = None
        ) -> None:
            captured.append((charproc, text_matrix))

    engine = _Engine()
    engine.show_type3_glyph("matrix", _Type3Font(), 65, "disp")  # type: ignore[arg-type]
    assert captured == [(cp, "matrix")]


def test_show_type3_glyph_no_op_when_charproc_missing() -> None:
    class _Type3Font:
        def get_char_proc(self, code: int) -> Any:
            return None

    engine = PDFStreamEngine()
    engine.show_type3_glyph(None, _Type3Font(), 99, None)


def test_show_type3_glyph_no_op_when_font_lacks_method() -> None:
    engine = PDFStreamEngine()
    engine.show_type3_glyph(None, object(), 0, None)
    engine.show_type3_glyph(None, None, 0, None)


# ---------- clip_to_rect ----------


def test_clip_to_rect_no_op_with_none_rectangle() -> None:
    engine = PDFStreamEngine()
    # Should not raise.
    engine.clip_to_rect(None)


def test_clip_to_rect_no_op_without_graphics_state() -> None:
    engine = PDFStreamEngine()
    rect = PDRectangle(0.0, 0.0, 10.0, 10.0)
    engine.clip_to_rect(rect)


def test_clip_to_rect_invokes_intersect_clipping_path() -> None:
    """A graphics-state frame that exposes ``intersect_clipping_path``
    receives the (transformed-or-raw) rectangle."""
    captured: list[Any] = []

    class _GS:
        def intersect_clipping_path(self, path: Any) -> None:
            captured.append(path)

    engine = PDFStreamEngine()
    engine._graphics_stack.append(_GS())
    rect = PDRectangle(0.0, 0.0, 10.0, 10.0)
    engine.clip_to_rect(rect)
    assert captured == [rect]


# ---------- process_page uses init_page ----------


def test_process_page_clears_stale_graphics_stack() -> None:
    """``process_page`` should call ``init_page`` and wipe any
    pre-existing graphics-state frames left from a prior run."""
    engine = _RecordingEngine()
    _register_all_text_ops(engine)
    engine._graphics_stack.append({"stale": True})
    page = PDPage()
    engine.process_page(page)
    assert engine.get_graphics_stack_size() == 0
