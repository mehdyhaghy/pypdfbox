from __future__ import annotations

from typing import Any, cast

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.state.set_line_width import SetLineWidth
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _GraphicsState:
    def __init__(self) -> None:
        self.line_width: float | None = None

    def set_line_width(self, width: float) -> None:
        self.line_width = width


class _Engine:
    def __init__(self) -> None:
        self.graphics_state = _GraphicsState()

    def get_graphics_state(self) -> _GraphicsState:
        return self.graphics_state


def test_wave298_get_line_width_returns_numeric_operand() -> None:
    width = SetLineWidth.get_line_width([COSInteger.get(3)])

    assert width is not None
    assert width.float_value() == 3.0


def test_wave298_get_line_width_skips_missing_or_non_number_operand() -> None:
    assert SetLineWidth.get_line_width([]) is None
    assert SetLineWidth.get_line_width([COSString(b"bad")]) is None


def test_wave298_process_updates_bound_graphics_state_for_number() -> None:
    engine = _Engine()
    processor = SetLineWidth()
    processor.set_context(cast(Any, engine))

    processor.process(Operator.get_operator("w"), [COSFloat(2.5)])

    assert engine.graphics_state.line_width == 2.5


def test_wave298_process_ignores_non_number_without_context_mutation() -> None:
    engine = _Engine()
    processor = SetLineWidth()
    processor.set_context(cast(Any, engine))

    processor.process(Operator.get_operator("w"), [COSString(b"bad")])

    assert engine.graphics_state.line_width is None
