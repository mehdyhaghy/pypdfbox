from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetFlatness(OperatorProcessor):
    """``i`` — Set the flatness tolerance in the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetFlatness``.

    Lite stub: registry-routing scaffold only — graphics-state flatness
    bookkeeping lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "i"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
