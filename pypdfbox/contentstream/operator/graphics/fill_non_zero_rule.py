from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class FillNonZeroRule(GraphicsOperatorProcessor):
    """``f`` — Fill the current path using the non-zero winding-number
    rule. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.FillNonZeroRule``
    (upstream lines 33–51).
    """

    OPERATOR_NAME = OperatorName.FILL_NON_ZERO

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.FILL_NON_ZERO


__all__ = ["FillNonZeroRule"]
