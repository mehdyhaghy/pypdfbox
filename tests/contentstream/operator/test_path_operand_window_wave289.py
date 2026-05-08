from __future__ import annotations

import logging

from _pytest.logging import LogCaptureFixture

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path.append_rectangle import AppendRectangle
from pypdfbox.contentstream.operator.path.curve_to import CurveTo
from pypdfbox.cos import COSBase, COSFloat, COSName


def test_append_rectangle_ignores_malformed_trailing_operands(
    caplog: LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    operands = [
        COSFloat(0.0),
        COSFloat(0.0),
        COSFloat(100.0),
        COSFloat(50.0),
        COSName("trailing"),
    ]

    AppendRectangle().process(Operator.get_operator("re"), operands)

    assert "AppendRectangle dispatched" in caplog.text


def test_append_rectangle_rejects_malformed_consumed_operand(
    caplog: LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )

    AppendRectangle().process(
        Operator.get_operator("re"),
        [COSFloat(0.0), COSName("bad"), COSFloat(100.0), COSFloat(50.0)],
    )

    assert "AppendRectangle dispatched" not in caplog.text


def test_curve_to_ignores_malformed_trailing_operands(
    caplog: LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    operands: list[COSBase] = [COSFloat(float(value)) for value in range(6)]
    operands.append(COSName("trailing"))

    CurveTo().process(Operator.get_operator("c"), operands)

    assert "CurveTo dispatched" in caplog.text


def test_curve_to_rejects_malformed_consumed_operand(
    caplog: LogCaptureFixture,
) -> None:
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    operands: list[COSBase] = [COSFloat(float(value)) for value in range(5)]
    operands.append(COSName("bad"))

    CurveTo().process(Operator.get_operator("c"), operands)

    assert "CurveTo dispatched" not in caplog.text
