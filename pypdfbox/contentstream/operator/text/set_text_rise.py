from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetTextRise(OperatorProcessor):
    """``Ts`` — Set the text rise. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetTextRise``.

    Lite stub: registry-routing scaffold only — the text-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "Ts"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
