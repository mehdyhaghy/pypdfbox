"""Round-out tests for :class:`SetStrokingRGB` (``RG``) and
:class:`SetNonStrokingRGB` (``rg``) — wave 1367.

Targets the engine-coupled behaviours that exercise the shared
``set_device_color`` helper for ``DeviceRGB`` (3 components):

* engine receives the resolved :class:`PDColor`,
* ``is_should_process_color_operators`` gate short-circuits,
* non-numeric operand → silent skip,
* short operand list → silent skip,
* extra trailing operands tolerated (only first 3 consumed),
* stroking vs non-stroking siblings are properly distinct.
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.contentstream import PDFStreamEngine
from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.color.set_non_stroking_rgb import (
    SetNonStrokingRGB,
)
from pypdfbox.contentstream.operator.color.set_stroking_rgb import (
    SetStrokingRGB,
)
from pypdfbox.cos import COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.graphics.color import PDColor, PDDeviceRGB


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


# ----- SetStrokingRGB (``RG``) -----------------------------------------


def test_stroking_rgb_engine_receives_resolved_color() -> None:
    engine = _Engine()
    processor = SetStrokingRGB(engine)

    processor.process(
        Operator.get_operator("RG"),
        [COSFloat(0.25), COSFloat(0.5), COSFloat(0.75)],
    )

    [color] = engine.stroking_calls
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_components() == pytest.approx([0.25, 0.5, 0.75])
    assert engine.non_stroking_calls == []


def test_stroking_rgb_mixed_int_and_float_operands() -> None:
    engine = _Engine()
    processor = SetStrokingRGB(engine)

    processor.process(
        Operator.get_operator("RG"),
        [COSInteger.get(0), COSFloat(0.5), COSInteger.get(1)],
    )

    [color] = engine.stroking_calls
    assert color.get_components() == pytest.approx([0.0, 0.5, 1.0])


def test_stroking_rgb_short_operand_list_silently_skips() -> None:
    engine = _Engine()
    processor = SetStrokingRGB(engine)

    processor.process(
        Operator.get_operator("RG"), [COSFloat(0.1), COSFloat(0.2)]
    )

    assert engine.stroking_calls == []


def test_stroking_rgb_non_numeric_first_operand_sets_invalid_color() -> None:
    # Upstream SetColor.process (via SetStrokingDeviceRGBColor) fails the
    # checkArrayTypesClass guard for a non-numeric operand and sets an
    # invalid PDColor([], null) (PDFBOX-5851) rather than leaving the
    # colour untouched. wave 1571 fixed set_device_color to match.
    engine = _Engine()
    processor = SetStrokingRGB(engine)

    processor.process(
        Operator.get_operator("RG"),
        [COSName.get_pdf_name("Bad"), COSFloat(0.2), COSFloat(0.3)],
    )

    [color] = engine.stroking_calls
    assert color.get_components() == []
    assert color.get_color_space() is None


def test_stroking_rgb_non_numeric_in_middle_sets_invalid_color() -> None:
    engine = _Engine()
    processor = SetStrokingRGB(engine)

    processor.process(
        Operator.get_operator("RG"),
        [COSFloat(0.1), COSString("bad"), COSFloat(0.3)],
    )

    [color] = engine.stroking_calls
    assert color.get_components() == []
    assert color.get_color_space() is None


def test_stroking_rgb_gate_short_circuits() -> None:
    engine = _Engine(process_color=False)
    processor = SetStrokingRGB(engine)

    processor.process(
        Operator.get_operator("RG"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )

    assert engine.stroking_calls == []


def test_stroking_rgb_extra_operands_tolerated() -> None:
    """Only first 3 are consumed for RGB; later operands are ignored."""
    engine = _Engine()
    processor = SetStrokingRGB(engine)

    processor.process(
        Operator.get_operator("RG"),
        [
            COSFloat(0.1),
            COSFloat(0.2),
            COSFloat(0.3),
            COSFloat(0.4),  # ignored
            COSString("trailing"),  # also ignored
        ],
    )

    [color] = engine.stroking_calls
    assert color.get_components() == pytest.approx([0.1, 0.2, 0.3])


def test_stroking_rgb_without_context_is_silent_no_op() -> None:
    SetStrokingRGB().process(
        Operator.get_operator("RG"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )


# ----- SetNonStrokingRGB (``rg``) --------------------------------------


def test_non_stroking_rgb_engine_receives_resolved_color() -> None:
    engine = _Engine()
    processor = SetNonStrokingRGB(engine)

    processor.process(
        Operator.get_operator("rg"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )

    [color] = engine.non_stroking_calls
    assert color.get_color_space() is PDDeviceRGB.INSTANCE
    assert color.get_components() == pytest.approx([0.1, 0.2, 0.3])
    assert engine.stroking_calls == []


def test_non_stroking_rgb_short_list_silently_skips() -> None:
    engine = _Engine()
    processor = SetNonStrokingRGB(engine)

    processor.process(Operator.get_operator("rg"), [])

    assert engine.non_stroking_calls == []


def test_non_stroking_rgb_gate_short_circuits() -> None:
    engine = _Engine(process_color=False)
    processor = SetNonStrokingRGB(engine)

    processor.process(
        Operator.get_operator("rg"),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )

    assert engine.non_stroking_calls == []


def test_stroking_and_non_stroking_rgb_classes_are_distinct() -> None:
    """``RG`` vs ``rg`` — case-sensitive split."""
    assert SetStrokingRGB is not SetNonStrokingRGB
    assert SetStrokingRGB.OPERATOR_NAME == "RG"
    assert SetNonStrokingRGB.OPERATOR_NAME == "rg"


@pytest.mark.parametrize(
    ("cls", "token", "stroking"),
    [
        (SetStrokingRGB, "RG", True),
        (SetNonStrokingRGB, "rg", False),
    ],
    ids=["stroking_RG", "non_stroking_rg"],
)
def test_rgb_routes_to_correct_engine_arm(
    cls: type, token: str, stroking: bool
) -> None:
    engine = _Engine()
    processor: Any = cls(engine)
    processor.process(
        Operator.get_operator(token),
        [COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)],
    )

    if stroking:
        assert len(engine.stroking_calls) == 1
        assert engine.non_stroking_calls == []
    else:
        assert len(engine.non_stroking_calls) == 1
        assert engine.stroking_calls == []
