from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetLineMiterLimit(OperatorProcessor):
    """``M`` — Set the miter limit in the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineMiterLimit``.

    Lite stub: registry-routing scaffold only — graphics-state
    miter-limit bookkeeping lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "M"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
