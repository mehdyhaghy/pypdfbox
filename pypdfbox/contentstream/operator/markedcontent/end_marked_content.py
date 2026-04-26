from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class EndMarkedContent(OperatorProcessor):
    """``EMC`` — End a marked-content sequence begun by ``BMC`` or
    ``BDC``. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.EndMarkedContentSequence``.

    Lite stub: registry-routing scaffold only — the marked-content
    bookkeeping arrives with the structure-tree cluster.
    """

    OPERATOR_NAME = "EMC"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
