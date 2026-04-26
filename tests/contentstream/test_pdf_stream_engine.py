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
    COSFloat,
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
    # show_text_string; ``ET`` fires set_text_matrix(None) +
    # set_text_line_matrix(None) + end_text.
    sequence = [name for name, _ in engine.events]
    assert sequence == [
        "set_text_matrix",
        "set_text_line_matrix",
        "begin_text",
        "set_font",
        "move_text_position",
        "show_text_string",
        "set_text_matrix",
        "set_text_line_matrix",
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
