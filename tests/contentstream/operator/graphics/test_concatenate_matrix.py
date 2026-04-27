from __future__ import annotations

from pypdfbox.contentstream.operator import Operator
from pypdfbox.contentstream.operator.graphics import ConcatenateMatrix
from pypdfbox.contentstream.operator.graphics.concatenate_matrix import (
    ConcatenateMatrix as ConcatenateMatrixDirect,
)
from pypdfbox.contentstream.operator.operator_registry import OperatorRegistry
from pypdfbox.cos import COSFloat, COSInteger


def test_class_attribute_operator_name() -> None:
    assert ConcatenateMatrix.OPERATOR_NAME == "cm"


def test_get_name_returns_cm() -> None:
    assert ConcatenateMatrix().get_name() == "cm"


def test_re_export_matches_module_class() -> None:
    assert ConcatenateMatrix is ConcatenateMatrixDirect


def test_process_with_six_operands_is_noop() -> None:
    handler = ConcatenateMatrix()
    handler.process(
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


def test_process_accepts_integer_operands() -> None:
    handler = ConcatenateMatrix()
    handler.process(
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


def test_process_accepts_empty_operands_list() -> None:
    """Lite stub does not enforce arity; engine layer will."""
    ConcatenateMatrix().process(Operator.get_operator("cm"), [])


def test_registered_in_default_registry() -> None:
    registry = OperatorRegistry()
    handler = registry.lookup("cm")
    assert handler is not None
    assert isinstance(handler, ConcatenateMatrix)
