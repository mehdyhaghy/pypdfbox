from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetLineJoinStyle(OperatorProcessor):
    """``j`` — Set the line join style in the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineJoinStyle``.

    Lite stub: registry-routing scaffold only — graphics-state
    line-join bookkeeping lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "j"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
