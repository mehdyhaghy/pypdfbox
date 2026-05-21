"""Hand-written tests for the ``GraphicsOperatorProcessor`` base — wave 1365.

Pins down the upstream-faithful surface: ``get_graphics_context`` is a
typed alias of :meth:`OperatorProcessor.get_context` (rendering-engine
narrowing arrives with the rendering cluster). The base is abstract via
the ``process`` abstract method inherited from ``OperatorProcessor``.
"""

from __future__ import annotations

from typing import ClassVar

import pytest

from pypdfbox.contentstream import Operator, PDFStreamEngine
from pypdfbox.contentstream.operator.graphics.graphics_operator_processor import (
    GraphicsOperatorProcessor,
)
from pypdfbox.contentstream.operator.operator_processor import (
    OperatorProcessor,
)
from pypdfbox.cos import COSBase


class _Concrete(GraphicsOperatorProcessor):
    OPERATOR_NAME: ClassVar[str] = "Xx"

    def __init__(
        self, context: PDFStreamEngine | None = None
    ) -> None:
        super().__init__(context)
        self.calls: list[tuple[Operator, list[COSBase]]] = []

    def process(  # type: ignore[override]
        self, operator: Operator, operands: list[COSBase]
    ) -> None:
        self.calls.append((operator, operands))


def test_subclass_of_operator_processor() -> None:
    assert issubclass(GraphicsOperatorProcessor, OperatorProcessor)


def test_cannot_instantiate_directly() -> None:
    with pytest.raises(TypeError):
        GraphicsOperatorProcessor()  # type: ignore[abstract]


def test_get_graphics_context_returns_none_when_unbound() -> None:
    p = _Concrete()
    assert p.get_graphics_context() is None
    assert p.get_context() is None


def test_get_graphics_context_returns_bound_engine() -> None:
    engine = PDFStreamEngine()
    p = _Concrete(engine)
    assert p.get_graphics_context() is engine
    # And it is the same object as ``get_context`` returns — narrowed type.
    assert p.get_graphics_context() is p.get_context()


def test_set_context_updates_both_accessors() -> None:
    engine = PDFStreamEngine()
    p = _Concrete()
    assert p.get_graphics_context() is None
    p.set_context(engine)
    assert p.get_graphics_context() is engine


def test_concrete_subclass_dispatches() -> None:
    p = _Concrete()
    op = Operator.get_operator("Xx")
    p.process(op, [])
    assert p.calls == [(op, [])]


def test_check_array_types_class_inherited_from_base() -> None:
    # Inherited helper still works for graphics-flavored subclasses.
    from pypdfbox.cos import COSFloat, COSInteger, COSName

    p = _Concrete()
    assert p.check_array_types_class(
        [COSFloat(1.0), COSInteger.get(2)], object
    )
    assert not p.check_array_types_class(
        [COSFloat(1.0), COSName.get_pdf_name("X")], COSFloat
    )
