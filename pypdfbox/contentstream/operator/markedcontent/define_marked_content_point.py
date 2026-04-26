from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class DefineMarkedContentPoint(OperatorProcessor):
    """``MP`` — Designate a marked-content point. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPoint``.

    Lite stub: registry-routing scaffold only — the marked-content
    bookkeeping arrives with the structure-tree cluster.
    """

    OPERATOR_NAME = "MP"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
