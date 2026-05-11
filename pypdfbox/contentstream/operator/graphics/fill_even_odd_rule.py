from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class FillEvenOddRule(GraphicsOperatorProcessor):
    """``f*`` — Fill the current path using the even-odd rule. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.FillEvenOddRule``
    (upstream lines 33–51).
    """

    OPERATOR_NAME = OperatorName.FILL_EVEN_ODD

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.FILL_EVEN_ODD


__all__ = ["FillEvenOddRule"]
