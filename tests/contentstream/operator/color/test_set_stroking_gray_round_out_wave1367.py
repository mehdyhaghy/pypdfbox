"""Round-out tests for :class:`SetStrokingGray` (``G``) and
:class:`SetNonStrokingGray` (``g``) — wave 1367.

The base tests cover registry registration and trivial happy paths; this
file targets the engine-coupled behaviours that exercise the shared
``set_device_color`` helper for ``DeviceGray``:

* engine receives the resolved :class:`PDColor` with one component,
* ``is_should_process_color_operators`` gate short-circuits,
* non-numeric operand → silent skip,
* empty operand list → silent skip,
* extra trailing operands are tolerated (only first 1 is consumed).
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_gray import (
    SetNonStrokingGray,
)
from pypdfbox.contentstream.operator.color.set_stroking_gray import (
    SetStrokingGray,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceGray


class _Engine(PDFStreamEngine):
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


# ----- SetStrokingGray (``G``) -----------------------------------------


def test_stroking_gray_engine_receives_resolved_color() -> None:
    engine = _Engine()
    processor = SetStrokingGray(engine)

    processor.process(Operator.get_operator("G"), [COSFloat(0.7)])

    assert len(engine.stroking_calls) == 1
    color = engine.stroking_calls[0]
    assert isinstance(color, PDColor)
    assert color.get_color_space() is PDDeviceGray.INSTANCE
    assert color.get_components() == pytest.approx([0.7])
    assert engine.non_stroking_calls == []


def test_stroking_gray_accepts_integer_operand() -> None:
    engine = _Engine()
    processor = SetStrokingGray(engine)

    processor.process(Operator.get_operator("G"), [COSInteger.get(1)])

    [color] = engine.stroking_calls
    assert color.get_components() == pytest.approx([1.0])


def test_stroking_gray_empty_operands_silently_skips() -> None:
    engine = _Engine()
    processor = SetStrokingGray(engine)

    processor.process(Operator.get_operator("G"), [])

    assert engine.stroking_calls == []


def test_stroking_gray_non_numeric_operand_sets_invalid_color() -> None:
    # Upstream SetColor.process sets an invalid PDColor([], null) for a
    # non-numeric operand (PDFBOX-5851); wave 1571 aligned
    # set_device_color with that rather than silently skipping.
    engine = _Engine()
    processor = SetStrokingGray(engine)

    processor.process(
        Operator.get_operator("G"), [COSName.get_pdf_name("Bogus")]
    )

    [color] = engine.stroking_calls
    assert color.get_components() == []
    assert color.get_color_space() is None


def test_stroking_gray_gate_short_circuits() -> None:
    engine = _Engine(process_color=False)
    processor = SetStrokingGray(engine)

    processor.process(Operator.get_operator("G"), [COSFloat(0.5)])

    assert engine.stroking_calls == []


def test_stroking_gray_ignores_extra_operands() -> None:
    """``G`` consumes only the leading operand; trailing entries ignored."""
    engine = _Engine()
    processor = SetStrokingGray(engine)

    processor.process(
        Operator.get_operator("G"),
        [COSFloat(0.5), COSFloat(0.9), COSString("trailing")],
    )

    [color] = engine.stroking_calls
    assert color.get_components() == pytest.approx([0.5])


def test_stroking_gray_without_context_is_silent_no_op() -> None:
    SetStrokingGray().process(
        Operator.get_operator("G"), [COSFloat(0.5)]
    )


# ----- SetNonStrokingGray (``g``) --------------------------------------


def test_non_stroking_gray_engine_receives_resolved_color() -> None:
    engine = _Engine()
    processor = SetNonStrokingGray(engine)

    processor.process(Operator.get_operator("g"), [COSFloat(0.3)])

    assert len(engine.non_stroking_calls) == 1
    color = engine.non_stroking_calls[0]
    assert color.get_color_space() is PDDeviceGray.INSTANCE
    assert color.get_components() == pytest.approx([0.3])
    assert engine.stroking_calls == []


def test_non_stroking_gray_short_operand_list_silently_skips() -> None:
    engine = _Engine()
    processor = SetNonStrokingGray(engine)

    processor.process(Operator.get_operator("g"), [])

    assert engine.non_stroking_calls == []


def test_non_stroking_gray_gate_short_circuits() -> None:
    engine = _Engine(process_color=False)
    processor = SetNonStrokingGray(engine)

    processor.process(Operator.get_operator("g"), [COSFloat(0.5)])

    assert engine.non_stroking_calls == []


def test_stroking_and_non_stroking_gray_classes_are_distinct() -> None:
    """Case-sensitive ``G`` (stroking) vs ``g`` (non-stroking) split."""
    assert SetStrokingGray is not SetNonStrokingGray
    assert SetStrokingGray.OPERATOR_NAME == "G"
    assert SetNonStrokingGray.OPERATOR_NAME == "g"


@pytest.mark.parametrize(
    ("cls", "token", "stroking"),
    [
        (SetStrokingGray, "G", True),
        (SetNonStrokingGray, "g", False),
    ],
    ids=["stroking_G", "non_stroking_g"],
)
def test_gray_routes_to_correct_engine_arm(
    cls: type, token: str, stroking: bool
) -> None:
    engine = _Engine()
    processor: Any = cls(engine)
    processor.process(Operator.get_operator(token), [COSFloat(0.42)])

    if stroking:
        assert len(engine.stroking_calls) == 1
        assert engine.non_stroking_calls == []
    else:
        assert len(engine.non_stroking_calls) == 1
        assert engine.stroking_calls == []
