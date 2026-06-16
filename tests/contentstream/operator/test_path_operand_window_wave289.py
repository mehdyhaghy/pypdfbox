from __future__ import annotations

import logging

from _pytest.logging import LogCaptureFixture

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.path.append_rectangle import AppendRectangle
from pypdfbox.contentstream.operator.path.curve_to import CurveTo
from pypdfbox.cos import COSBase, COSFloat, COSName


def test_append_rectangle_rejects_malformed_trailing_operands(
    caplog: LogCaptureFixture,
) -> None:
    """Upstream ``AppendRectangleToPath`` calls ``checkArrayTypesClass``
    over the WHOLE operand list, so a trailing non-number (``x y w h /N
    re``) makes the operator a silent no-op — NOT accepted-with-trailing-
    ignored (the divergence wave 1572 found, converged wave 1573)."""
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

    assert "AppendRectangle dispatched" not in caplog.text


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


def test_curve_to_rejects_malformed_trailing_operands(
    caplog: LogCaptureFixture,
) -> None:
    """Upstream ``CurveTo`` calls ``checkArrayTypesClass`` over the WHOLE
    operand list, so a trailing non-number (``x1 y1 x2 y2 x3 y3 /N c``)
    makes the operator a silent no-op — NOT accepted-with-trailing-
    ignored (the divergence wave 1572 found, converged wave 1573)."""
    caplog.set_level(
        logging.DEBUG,
        logger="pypdfbox.contentstream.operator.operator_processor",
    )
    operands: list[COSBase] = [COSFloat(float(value)) for value in range(6)]
    operands.append(COSName("trailing"))

    CurveTo().process(Operator.get_operator("c"), operands)

    assert "CurveTo dispatched" not in caplog.text


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
