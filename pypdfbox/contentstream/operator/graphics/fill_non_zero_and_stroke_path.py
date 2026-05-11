from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class FillNonZeroAndStrokePath(GraphicsOperatorProcessor):
    """``B`` — Fill and then stroke the path, using the non-zero
    winding-number rule to determine the region to fill. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.FillNonZeroAndStrokePath``
    (upstream lines 35–53).
    """

    OPERATOR_NAME = OperatorName.FILL_NON_ZERO_AND_STROKE

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.FILL_NON_ZERO_AND_STROKE


__all__ = ["FillNonZeroAndStrokePath"]
