from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetRenderingIntent(OperatorProcessor):
    """``ri`` — Set the colour rendering intent in the graphics state.
    Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetRenderingIntent``.

    Lite stub: registry-routing scaffold only — rendering-intent
    bookkeeping lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "ri"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
