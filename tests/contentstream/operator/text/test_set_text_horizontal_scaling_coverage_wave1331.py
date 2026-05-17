"""Coverage round-out for ``SetTextHorizontalScaling`` (``Tz``).

Targets the defensive early-return branches in ``process``:

* missing-operand → ``MissingOperandException``
* non-numeric operand → silent return
* ``context is None`` → silent return
* ``text_state`` attribute missing → silent return
* ``text_state()`` returns ``None`` → silent return
* ``set_horizontal_scaling`` setter missing → silent return
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator import MissingOperandException
from pypdfbox.contentstream.operator.text.set_text_horizontal_scaling import (
    SetTextHorizontalScaling,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString


class _TextState:
    """Minimal text-state stand-in with a recordable scaling setter."""

    def __init__(self) -> None:
        self.scaling: float | None = None

    def set_horizontal_scaling(self, value: float) -> None:
        self.scaling = value


class _GraphicsStateWithTextState:
    """Graphics-state stub returning a controllable text-state."""

    def __init__(self, text_state: Any) -> None:
        self._text_state = text_state

    def get_text_state(self) -> Any:
        return self._text_state


class _ScalingSpyEngine(PDFStreamEngine):
    """Engine returning a real text-state via the graphics-state hook."""

    def __init__(self, text_state: Any) -> None:
        super().__init__()
        self._gs = _GraphicsStateWithTextState(text_state)

    def get_graphics_state(self) -> Any:
        return self._gs


def test_process_with_no_operands_raises_missing_operand() -> None:
    """``Tz`` requires one numeric operand — empty list raises."""
    processor = SetTextHorizontalScaling()
    with pytest.raises(MissingOperandException):
        processor.process(Operator.get_operator("Tz"), [])


def test_process_with_non_number_operand_returns_silently() -> None:
    """Mirrors upstream leniency for malformed streams: any non-number
    operand short-circuits without raising and without touching the
    text-state setter."""
    text_state = _TextState()
    engine = _ScalingSpyEngine(text_state)
    processor = SetTextHorizontalScaling(engine)
    processor.process(
        Operator.get_operator("Tz"),
        [COSName.get_pdf_name("Bogus")],
    )
    assert text_state.scaling is None
    # COSString also fails the COSNumber instance check.
    processor.process(Operator.get_operator("Tz"), [COSString("nope")])
    assert text_state.scaling is None


def test_process_without_context_is_silent() -> None:
    """``context is None`` short-circuits — never touches a setter."""
    processor = SetTextHorizontalScaling()
    assert processor.get_context() is None
    processor.process(Operator.get_operator("Tz"), [COSFloat(2.5)])


def test_process_when_text_state_accessor_missing_is_silent() -> None:
    """If the graphics-state lacks ``get_text_state``, the operator
    silently returns rather than raising ``AttributeError``."""

    class _GsNoTextState:
        pass

    class _EngineNoTextState(PDFStreamEngine):
        def get_graphics_state(self) -> Any:
            return _GsNoTextState()

    engine = _EngineNoTextState()
    processor = SetTextHorizontalScaling(engine)
    # Should not raise.
    processor.process(Operator.get_operator("Tz"), [COSFloat(0.75)])


def test_process_when_text_state_is_none_is_silent() -> None:
    """If ``get_text_state()`` returns ``None``, no setter is called."""
    engine = _ScalingSpyEngine(None)
    processor = SetTextHorizontalScaling(engine)
    processor.process(Operator.get_operator("Tz"), [COSFloat(0.5)])


def test_process_when_setter_missing_is_silent() -> None:
    """A text-state object without ``set_horizontal_scaling`` is OK."""

    class _BareTextState:
        pass

    engine = _ScalingSpyEngine(_BareTextState())
    processor = SetTextHorizontalScaling(engine)
    processor.process(Operator.get_operator("Tz"), [COSFloat(1.25)])


def test_process_invokes_setter_with_float_value() -> None:
    """Happy path: setter is called with the operand's float value."""
    text_state = _TextState()
    engine = _ScalingSpyEngine(text_state)
    processor = SetTextHorizontalScaling(engine)
    processor.process(Operator.get_operator("Tz"), [COSFloat(1.5)])
    assert text_state.scaling == pytest.approx(1.5)


def test_process_accepts_cos_integer_operand() -> None:
    """``COSInteger`` is a ``COSNumber`` — gets widened to ``float``."""
    text_state = _TextState()
    engine = _ScalingSpyEngine(text_state)
    processor = SetTextHorizontalScaling(engine)
    processor.process(Operator.get_operator("Tz"), [COSInteger.get(2)])
    assert text_state.scaling == pytest.approx(2.0)


def test_get_name_returns_tz_constant() -> None:
    """``get_name`` returns the ``Tz`` operator token."""
    assert SetTextHorizontalScaling().get_name() == "Tz"
    assert SetTextHorizontalScaling.OPERATOR_NAME == "Tz"
