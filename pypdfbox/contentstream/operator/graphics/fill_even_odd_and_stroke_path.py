from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class FillEvenOddAndStrokePath(GraphicsOperatorProcessor):
    """``B*`` — Fill and then stroke the path, using the even-odd rule
    to determine the region to fill. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.FillEvenOddAndStrokePath``
    (upstream lines 33–51).
    """

    OPERATOR_NAME = OperatorName.FILL_EVEN_ODD_AND_STROKE

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.FILL_EVEN_ODD_AND_STROKE


__all__ = ["FillEvenOddAndStrokePath"]
