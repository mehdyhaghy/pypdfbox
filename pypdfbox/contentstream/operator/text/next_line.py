from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class NextLine(OperatorProcessor):
    """``T*`` — Move to the start of the next line. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.NextLine``.

    Lite stub: registry-routing scaffold only — the text-positioning
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "T*"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
