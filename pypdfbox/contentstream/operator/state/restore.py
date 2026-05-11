"""``Q`` — Restore the graphics state.

Mirrors ``org.apache.pdfbox.contentstream.operator.state.Restore`` (PDFBox 3.x;
Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Restore.java``).
"""

from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from ..operator_processor import OperatorProcessor
from .empty_graphics_stack_exception import EmptyGraphicsStackException


class Restore(OperatorProcessor):
    """``Q`` — pop the top graphics-state frame, but never the last one
    (PDFBOX-161 ``EmptyGraphicsStackException``)."""

    OPERATOR_NAME = OperatorName.RESTORE

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator, operands
        context = self._context
        if context is None:
            return
        if context.get_graphics_stack_size() > 1:
            context.restore_graphics_state()
        else:
            raise EmptyGraphicsStackException()

    def get_name(self) -> str:
        return OperatorName.RESTORE


__all__ = ["Restore"]
