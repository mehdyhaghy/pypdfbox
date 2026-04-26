from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetNonStrokingColorN(OperatorProcessor):
    """``scn`` — Same as ``SCN`` but for non-stroking operations.
    Mirrors ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColorN``.

    Lite stub: registry-routing scaffold only — the colour-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "scn"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
