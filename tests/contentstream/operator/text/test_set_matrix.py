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
        self.text_matrix = list(matrix) if matrix is not None else None

    def set_text_line_matrix(self, matrix: list[float] | None) -> None:
        self.text_line_matrix = list(matrix) if matrix is not None else None


def _bind() -> tuple[SetMatrix, _Spy]:
    p = SetMatrix()
    engine = _Spy()
    engine.add_operator(p)
    return p, engine


def _nums(values: list[float]) -> list:
    return [COSFloat(v) for v in values]


def test_get_name() -> None:
    assert SetMatrix().get_name() == "Tm"


def test_process_sets_both_matrices_to_supplied_values() -> None:
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tm"), _nums([2.0, 0.0, 0.0, 3.0, 100.0, 200.0])
    )
    assert engine.text_matrix == [2.0, 0.0, 0.0, 3.0, 100.0, 200.0]
    assert engine.text_line_matrix == [2.0, 0.0, 0.0, 3.0, 100.0, 200.0]


def test_process_accepts_cos_integer_operands() -> None:
    p, engine = _bind()
    operands = [COSInteger.get(i) for i in (1, 0, 0, 1, 5, 6)]
    p.process(Operator.get_operator("Tm"), operands)
    assert engine.text_matrix == [1.0, 0.0, 0.0, 1.0, 5.0, 6.0]


def test_text_and_text_line_matrices_are_independent_copies() -> None:
    """Upstream constructs the line matrix via ``new Matrix(a,b,c,d,e,f)``
    on its own — pypdfbox passes a copy. Mutating one must not affect
    the other."""
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tm"), _nums([1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    )
    assert engine.text_matrix is not engine.text_line_matrix


def test_fewer_than_six_operands_raises() -> None:
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tm"), _nums([1.0, 0.0, 0.0, 1.0, 0.0]))


def test_zero_operands_raises() -> None:
    p, _ = _bind()
    with pytest.raises(MissingOperandException):
        p.process(Operator.get_operator("Tm"), [])


def test_non_number_operand_silently_drops() -> None:
    p, engine = _bind()
    bad = [
        COSFloat(1.0),
        COSString(b"x"),
        COSFloat(0.0),
        COSFloat(1.0),
        COSFloat(0.0),
        COSFloat(0.0),
    ]
    p.process(Operator.get_operator("Tm"), bad)
    assert engine.text_matrix is None


def test_extra_operands_are_ignored() -> None:
    p, engine = _bind()
    p.process(
        Operator.get_operator("Tm"),
        _nums([1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 999.0]),
    )
    assert engine.text_matrix == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_re_export_canonical() -> None:
    from pypdfbox.contentstream.operator.text import SetMatrix as Reexport

    assert Reexport is SetMatrix
