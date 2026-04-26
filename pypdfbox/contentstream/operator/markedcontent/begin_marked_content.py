from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class BeginMarkedContent(OperatorProcessor):
    """``BMC`` — Begin a marked-content sequence. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.BeginMarkedContentSequence``.

    Lite stub: registry-routing scaffold only — the marked-content
    bookkeeping arrives with the structure-tree cluster.
    """

    OPERATOR_NAME = "BMC"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
