from __future__ import annotations

from typing import Any

from pypdfbox.contentstream import (
    WIND_NON_ZERO,
    PDFGraphicsStreamEngine,
    PDFStreamEngine,
)
from pypdfbox.cos import COSBase, COSInteger, COSName, COSString


class _RecordingGraphicsEngine(PDFGraphicsStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[tuple[str, tuple[Any, ...]]] = []
        self._current: tuple[float, float] | None = None

    def append_rectangle(
        self,
        p0: tuple[float, float],
        p1: tuple[float, float],
        p2: tuple[float, float],
        p3: tuple[float, float],
    ) -> None:
        self.events.append(("append_rectangle", (p0, p1, p2, p3)))
        self._current = p0

    def draw_image(self, pd_image: Any) -> None:
        self.events.append(("draw_image", (pd_image,)))

    def clip(self, winding_rule: int) -> None:
        self.events.append(("clip", (winding_rule,)))

    def move_to(self, x: float, y: float) -> None:
        self.events.append(("move_to", (x, y)))
        self._current = (x, y)

    def line_to(self, x: float, y: float) -> None:
        self.events.append(("line_to", (x, y)))
        self._current = (x, y)

    def curve_to(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> None:
        self.events.append(("curve_to", (x1, y1, x2, y2, x3, y3)))
        self._current = (x3, y3)

    def get_current_point(self) -> tuple[float, float] | None:
        return self._current

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


def _ints(*values: int) -> list[COSBase]:
    return [COSInteger.get(value) for value in values]


def test_stream_engine_to_float_returns_none_for_non_number() -> None:
    assert PDFStreamEngine._to_float(COSString(b"bad")) is None


def test_graphics_engine_uses_first_operands_and_ignores_trailing_noise() -> None:
    engine = _RecordingGraphicsEngine()

    engine.process_operator("c", [*_ints(1, 2, 3, 4, 5, 6), COSString(b"noise")])

    assert engine.events == [("curve_to", (1.0, 2.0, 3.0, 4.0, 5.0, 6.0))]


def test_graphics_engine_skips_replicated_initial_curve_without_current_point() -> None:
    engine = _RecordingGraphicsEngine()

    engine.process_operator("v", _ints(1, 2, 3, 4))

    assert engine.events == []


def test_graphics_engine_skips_shading_fill_when_operand_is_not_name() -> None:
    engine = _RecordingGraphicsEngine()

    engine.process_operator("sh", [COSString(b"not-a-name")])

    assert engine.events == []


def test_graphics_engine_close_fill_and_stroke_routes_close_then_nonzero() -> None:
    engine = _RecordingGraphicsEngine()

    engine.process_operator("b", None)

    assert engine.events == [
        ("close_path", ()),
        ("fill_and_stroke_path", (WIND_NON_ZERO,)),
    ]
