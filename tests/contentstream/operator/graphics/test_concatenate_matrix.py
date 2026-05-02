from __future__ import annotations

import pytest

from pypdfbox.contentstream import (
    MissingOperandException,
    Operator,
    PDFStreamEngine,
)
from pypdfbox.contentstream.operator.graphics import ConcatenateMatrix
from pypdfbox.contentstream.operator.graphics.concatenate_matrix import (
    ConcatenateMatrix as ConcatenateMatrixDirect,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat, COSInteger, COSString


class _Spy(PDFStreamEngine):
    def __init__(self) -> None:
        super().__init__()
        self.transforms: list[tuple[float, ...]] = []

    def transform(self, matrix: object) -> None:
        # Store as tuple for stable equality comparisons.
        self.transforms.append(tuple(matrix))  # type: ignore[arg-type]


def _bind() -> tuple[ConcatenateMatrix, _Spy]:
    p = ConcatenateMatrix()
    engine = _Spy()
    engine.add_operator(p)
    return p, engine


def test_class_attribute_operator_name() -> None:
    assert ConcatenateMatrix.OPERATOR_NAME == "cm"


def test_get_name_returns_cm() -> None:
    assert ConcatenateMatrix().get_name() == "cm"


def test_re_export_matches_module_class() -> None:
    assert ConcatenateMatrix is ConcatenateMatrixDirect


def test_process_six_operands_dispatches_transform() -> None:
    p, engine = _bind()
    p.process(
        Operator.get_operator("cm"),
        [
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(1.0),
            COSFloat(50.0),
            COSFloat(75.0),
        ],
    )
    assert engine.transforms == [(1.0, 0.0, 0.0, 1.0, 50.0, 75.0)]


def test_process_accepts_integer_operands() -> None:
    p, engine = _bind()
    p.process(
        Operator.get_operator("cm"),
        [
            COSInteger.get(1),
            COSInteger.get(0),
            COSInteger.get(0),
            COSInteger.get(1),
            COSInteger.get(0),
            COSInteger.get(0),
        ],
    )
    assert engine.transforms == [(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)]


def test_zero_operands_raises_missing_operand() -> None:
    """Parity with upstream ``Concatenate`` — fewer than six operands
    raises ``MissingOperandException`` (Java's
    ``arguments.size() < 6`` guard)."""
    handler = ConcatenateMatrix()
    with pytest.raises(MissingOperandException):
        handler.process(Operator.get_operator("cm"), [])


def test_fewer_than_six_operands_raises_missing_operand() -> None:
    handler = ConcatenateMatrix()
    with pytest.raises(MissingOperandException):
        handler.process(
            Operator.get_operator("cm"),
            [COSFloat(1.0), COSFloat(0.0), COSFloat(0.0), COSFloat(1.0), COSFloat(0.0)],
        )


def test_non_number_operand_silently_drops() -> None:
    """Parity with upstream ``checkArrayTypesClass`` — a non-``COSNumber``
    operand causes a silent skip rather than an exception."""
    p, engine = _bind()
    bad = [
        COSFloat(1.0),
        COSString(b"x"),
        COSFloat(0.0),
        COSFloat(1.0),
        COSFloat(0.0),
        COSFloat(0.0),
    ]
    p.process(Operator.get_operator("cm"), bad)
    assert engine.transforms == []


def test_extra_operands_are_ignored() -> None:
    p, engine = _bind()
    p.process(
        Operator.get_operator("cm"),
        [
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(999.0),
        ],
    )
    assert engine.transforms == [(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)]


def test_process_without_bound_engine_is_noop() -> None:
    """A registry-only ``ConcatenateMatrix`` (never bound to a
    ``PDFStreamEngine``) must still validate operands without raising
    on the dispatch path — the engine hook is simply skipped."""
    handler = ConcatenateMatrix()
    handler.process(
        Operator.get_operator("cm"),
        [
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(1.0),
            COSFloat(0.0),
            COSFloat(0.0),
        ],
    )


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("cm")
    assert handler is not None
    assert isinstance(handler, ConcatenateMatrix)
