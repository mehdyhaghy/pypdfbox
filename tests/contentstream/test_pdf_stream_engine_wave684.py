from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import (
    Operator,
    OperatorProcessor,
    PDFGraphicsStreamEngine,
    PDFStreamEngine,
)
from pypdfbox.cos import COSBase, COSInteger, COSName


class _ExceptionRecordingEngine(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.exceptions: list[tuple[str, str]] = []

    def operator_exception(
        self,
        operator: Operator,
        operands: list[COSBase],
        exception: OSError,
    ) -> None:
        self.exceptions.append((operator.get_name(), str(exception)))


class _RecordingGraphicsEngine(PDFGraphicsStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, tuple[Any, ...]]] = []
        self.current: tuple[float, float] | None = None

    def append_rectangle(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
    ) -> None:
        self.events.append(("append_rectangle", (p0, p1, p2, p3)))

    def draw_image(self, pd_image: Any) -> None:
        self.events.append(("draw_image", (pd_image,)))

    def clip(self, winding_rule: int) -> None:
        self.events.append(("clip", (winding_rule,)))

    def move_to(self, x: float, y: float) -> None:
        self.current = (x, y)
        self.events.append(("move_to", (x, y)))

    def line_to(self, x: float, y: float) -> None:
        self.current = (x, y)
        self.events.append(("line_to", (x, y)))

    def curve_to(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> None:
        self.current = (x3, y3)
        self.events.append(("curve_to", (x1, y1, x2, y2, x3, y3)))

    def get_current_point(self) -> tuple[float, float] | None:
        return self.current

    def close_path(self) -> None:
        self.events.append(("close_path", ()))

    def end_path(self) -> None:
        self.events.append(("end_path", ()))

    def stroke_path(self) -> None:
        self.events.append(("stroke_path", ()))

    def fill_path(self, winding_rule: int) -> None:
        self.events.append(("fill_path", (winding_rule,)))

    def fill_and_stroke_path(self, winding_rule: int) -> None:
        self.events.append(("fill_and_stroke_path", (winding_rule,)))

    def shading_fill(self, shading_name: COSName) -> None:
        self.events.append(("shading_fill", (shading_name,)))


def test_wave684_inline_image_stub_oserror_is_triaged_after_show(
    monkeypatch: Any,
) -> None:
    class InlineImage:
        def __init__(self, *args: Any) -> None:
            pass

    class BadInlineImageStub(OperatorProcessor):
        def process(self, operator: Operator, operands: list[COSBase]) -> None:
            raise OSError("stub failed")

        def get_name(self) -> str:
            return "BI"

    monkeypatch.setattr(
        "pypdfbox.pdmodel.graphics.image.pd_inline_image.PDInlineImage",
        InlineImage,
    )
    engine = _ExceptionRecordingEngine()
    engine.add_operator(BadInlineImageStub())

    engine.process_operator("BI", [])

    assert engine.exceptions == [("BI", "stub failed")]


def test_wave684_show_form_treats_bad_length_as_empty() -> None:
    class BadLengthCOS:
        def get_length(self) -> object:
            return object()

    class Form:
        def get_cos_object(self) -> BadLengthCOS:
            return BadLengthCOS()

    class Engine(PDFStreamEngine):
        def __init__(self) -> None:
            super().__init__()
            self.processed = False

        def process_stream(self, content_stream: Any) -> None:
            self.processed = True

    engine = Engine()
    engine._current_page = object()

    engine.show_form(Form())  # type: ignore[arg-type]

    assert engine.processed is False


def test_wave684_decode_codes_stops_when_font_reader_raises_oserror() -> None:
    class FailingFont:
        def read_code(self, src: Any) -> int:
            raise OSError("bad font program")

    assert PDFStreamEngine._decode_codes_via_font(b"abc", FailingFont()) == []


def test_wave684_to_float_accepts_cos_number() -> None:
    assert PDFStreamEngine._to_float(COSInteger.get(7)) == 7.0


def test_wave684_graphics_process_operator_none_operands_are_empty() -> None:
    engine = _RecordingGraphicsEngine()

    engine.process_operator("m", None)

    assert engine.events == []


def test_wave684_graphics_drops_short_or_non_numeric_path_operands() -> None:
    engine = _RecordingGraphicsEngine()

    engine.process_operator("l", [COSInteger.get(1)])
    engine.process_operator("c", [COSInteger.get(1), COSInteger.get(2)])
    engine.process_operator("v", [COSInteger.get(1), COSInteger.get(2)])
    engine.process_operator("y", [COSInteger.get(1), COSInteger.get(2)])
    engine.process_operator("re", [COSInteger.get(1), COSInteger.get(2)])
    engine.process_operator(
        "c",
        [
            COSInteger.get(1),
            COSName.get_pdf_name("Bad"),
            COSInteger.get(3),
            COSInteger.get(4),
            COSInteger.get(5),
            COSInteger.get(6),
        ],
    )

    assert engine.events == []


def test_wave684_graphics_v_drops_when_current_point_missing() -> None:
    engine = _RecordingGraphicsEngine()

    engine.process_operator(
        "v",
        [COSInteger.get(1), COSInteger.get(2), COSInteger.get(3), COSInteger.get(4)],
    )

    assert engine.events == []
