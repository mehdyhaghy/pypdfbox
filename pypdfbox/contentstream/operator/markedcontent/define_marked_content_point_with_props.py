from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class DefineMarkedContentPointWithProps(OperatorProcessor):
    """``DP`` — Designate a marked-content point with an associated
    property list. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPointWithProperties``.

    Lite stub: registry-routing scaffold only — the marked-content
    bookkeeping arrives with the structure-tree cluster.
    """

    OPERATOR_NAME = "DP"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
