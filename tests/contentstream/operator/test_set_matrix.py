from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.text import SetMatrix
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.text_matrix: list[float] | None = None
        self.text_line_matrix: list[float] | None = None

    def set_text_matrix(self, matrix: list[float] | None) -> None:
        self.text_matrix = matrix

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        self.text_line_matrix = matrix


def _bind(processor: SetMatrix) -> _Spy:
    engine = _Spy()
    engine.add_operator(processor)
    return engine


def test_get_name() -> None:
    assert SetMatrix().get_name() == "Tm"


def test_process_passes_six_floats_to_both_matrices() -> None:
    p = SetMatrix()
    engine = _bind(p)
    operands = [
        COSInteger.get(1),
        COSInteger.get(0),
        COSInteger.get(0),
        COSInteger.get(1),
        COSFloat(100.0),
        COSFloat(200.0),
    ]
    p.process(Operator.get_operator("Tm"), operands)
    assert engine.text_matrix == [1.0, 0.0, 0.0, 1.0, 100.0, 200.0]
    assert engine.text_line_matrix == [1.0, 0.0, 0.0, 1.0, 100.0, 200.0]
    # Defensive copy: the two lists should be independent.
    assert engine.text_matrix is not engine.text_line_matrix


def test_too_few_operands_raises() -> None:
    p = SetMatrix()
    _bind(p)
    with pytest.raises(MissingOperandException):
        p.process(
            Operator.get_operator("Tm"),
            [COSInteger.get(1), COSInteger.get(0)],
        )


def test_wrong_type_silently_drops() -> None:
    p = SetMatrix()
    engine = _bind(p)
    p.process(
        Operator.get_operator("Tm"),
        [
            COSInteger.get(1),
            COSInteger.get(0),
            COSInteger.get(0),
            COSInteger.get(1),
            COSString(b"oops"),
            COSFloat(0.0),
        ],
    )
    assert engine.text_matrix is None
