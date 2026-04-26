from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetTextRenderingMode(OperatorProcessor):
    """``Tr`` — Set the text rendering mode. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetTextRenderingMode``.

    Lite stub: registry-routing scaffold only — the text-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "Tr"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
