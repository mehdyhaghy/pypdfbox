"""Round-out tests for :class:`SetStrokingCMYK` (``K``) and
:class:`SetNonStrokingCMYK` (``k``) — wave 1367.

The base tests already cover registry registration and trivial happy paths;
this file targets the engine-coupled scenarios that exercise the shared
``set_device_color`` helper:

* engine receives the resolved :class:`PDColor` instance,
* ``is_should_process_color_operators`` gate short-circuits,
* a non-numeric operand silently skips,
* short operand lists silently skip (no exception),
* extra trailing operands are tolerated (only the first 4 are consumed),
* no-context standalone use is a no-op.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_cmyk import (
    SetNonStrokingCMYK,
)
from pypdfbox.contentstream.operator.color.set_stroking_cmyk import (
    SetStrokingCMYK,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceCMYK


class _Engine(PDFStreamEngine):
    """Minimal engine that records stroking + non-stroking color calls."""

    def __init__(self, *, process_color: bool = True) -> None:
        super().__init__()
        self._process_color: bool = process_color
        self.stroking_calls: list[PDColor] = []
        self.non_stroking_calls: list[PDColor] = []

    def is_should_process_color_operators(self) -> bool:
        return self._process_color

    def set_stroking_color(self, color: PDColor) -> None:
        self.stroking_calls.append(color)

    def set_non_stroking_color(self, color: PDColor) -> None:
        self.non_stroking_calls.append(color)


# ----- SetStrokingCMYK (``K``) -----------------------------------------


def test_stroking_cmyk_engine_receives_resolved_color() -> None:
    engine = _Engine()
    processor = SetStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("K"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
    )

    assert len(engine.stroking_calls) == 1
    color = engine.stroking_calls[0]
    assert isinstance(color, PDColor)
    assert color.get_color_space() is PDDeviceCMYK.INSTANCE
    assert color.get_components() == pytest.approx([0.1, 0.2, 0.3, 0.4])
    assert engine.non_stroking_calls == []


def test_stroking_cmyk_accepts_integer_operands() -> None:
    """Integer operands resolve via ``COSNumber.float_value``."""
    engine = _Engine()
    processor = SetStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("K"),
        [
            COSInteger.get(0),
            COSInteger.get(1),
            COSInteger.get(0),
            COSInteger.get(1),
        ],
    )

    [color] = engine.stroking_calls
    assert color.get_components() == pytest.approx([0.0, 1.0, 0.0, 1.0])


def test_stroking_cmyk_short_operand_list_silently_skips() -> None:
    """Fewer than four operands → no call, no raise."""
    engine = _Engine()
    processor = SetStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("K"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )

    assert engine.stroking_calls == []


def test_stroking_cmyk_non_numeric_operand_silently_skips() -> None:
    """A non-:class:`COSNumber` operand within the first 4 aborts."""
    engine = _Engine()
    processor = SetStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("K"),
        [
            COSFloat(0.1),
            COSFloat(0.2),
            COSName.get_pdf_name("Bogus"),
            COSFloat(0.4),
        ],
    )

    assert engine.stroking_calls == []


def test_stroking_cmyk_gate_short_circuits() -> None:
    """Type3 / uncoloured tiling pattern path — the gate is ``False``."""
    engine = _Engine(process_color=False)
    processor = SetStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("K"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
    )

    assert engine.stroking_calls == []


def test_stroking_cmyk_ignores_extra_trailing_operands() -> None:
    """Only the first ``component_count`` (=4) operands are consumed."""
    engine = _Engine()
    processor = SetStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("K"),
        [
            COSFloat(0.1),
            COSFloat(0.2),
            COSFloat(0.3),
            COSFloat(0.4),
            COSFloat(0.5),  # ignored
            COSString("trailing"),  # also ignored
        ],
    )

    [color] = engine.stroking_calls
    assert color.get_components() == pytest.approx([0.1, 0.2, 0.3, 0.4])


def test_stroking_cmyk_without_context_is_silent_no_op() -> None:
    """Registry-standalone use: no engine bound, no exception."""
    processor = SetStrokingCMYK()
    processor.process(
        Operator.get_operator("K"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
    )


def test_stroking_cmyk_set_context_late_binding_works() -> None:
    """An instance constructed standalone can be bound later."""
    processor = SetStrokingCMYK()
    engine = _Engine()
    processor.set_context(engine)
    processor.process(
        Operator.get_operator("K"),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0), COSFloat(1.0)],
    )
    assert len(engine.stroking_calls) == 1


# ----- SetNonStrokingCMYK (``k``) --------------------------------------


def test_non_stroking_cmyk_engine_receives_resolved_color() -> None:
    engine = _Engine()
    processor = SetNonStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("k"),
        [COSFloat(0.5), COSFloat(0.5), COSFloat(0.5), COSFloat(0.5)],
    )

    assert len(engine.non_stroking_calls) == 1
    color = engine.non_stroking_calls[0]
    assert color.get_color_space() is PDDeviceCMYK.INSTANCE
    assert color.get_components() == pytest.approx([0.5, 0.5, 0.5, 0.5])
    assert engine.stroking_calls == []


def test_non_stroking_cmyk_short_operand_list_silently_skips() -> None:
    engine = _Engine()
    processor = SetNonStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("k"), [COSFloat(0.1), COSFloat(0.2)]
    )

    assert engine.non_stroking_calls == []


def test_non_stroking_cmyk_gate_short_circuits() -> None:
    engine = _Engine(process_color=False)
    processor = SetNonStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("k"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
    )

    assert engine.non_stroking_calls == []


def test_non_stroking_cmyk_does_not_route_to_stroking_arm() -> None:
    """``k`` is the non-stroking sibling — must never touch stroking."""
    engine = _Engine()
    processor = SetNonStrokingCMYK(engine)

    processor.process(
        Operator.get_operator("k"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3), COSFloat(0.4)],
    )

    assert engine.stroking_calls == []
    assert len(engine.non_stroking_calls) == 1


def test_stroking_and_non_stroking_classes_are_distinct() -> None:
    assert SetStrokingCMYK is not SetNonStrokingCMYK
    assert SetStrokingCMYK.OPERATOR_NAME != SetNonStrokingCMYK.OPERATOR_NAME
    assert SetStrokingCMYK.OPERATOR_NAME == "K"
    assert SetNonStrokingCMYK.OPERATOR_NAME == "k"


@pytest.mark.parametrize(
    ("cls", "token", "stroking"),
    [
        (SetStrokingCMYK, "K", True),
        (SetNonStrokingCMYK, "k", False),
    ],
    ids=["stroking_K", "non_stroking_k"],
)
def test_cmyk_get_context_round_trips(
    cls: type, token: str, stroking: bool
) -> None:
    """``get_context`` returns the engine bound at construction time."""
    engine = _Engine()
    processor: Any = cls(engine)
    assert processor.get_context() is engine
    # Smoke: process once, depending on stroking/non-stroking sibling.
    processor.process(
        Operator.get_operator(token),
        [COSFloat(0.0), COSFloat(0.0), COSFloat(0.0), COSFloat(0.0)],
    )
    routed = engine.stroking_calls if stroking else engine.non_stroking_calls
    assert len(routed) == 1
