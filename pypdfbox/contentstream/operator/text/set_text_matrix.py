from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetTextMatrix(OperatorProcessor):
    """``Tm`` — Set the text matrix and text-line matrix. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetMatrix``.

    Lite stub used by :class:`OperatorRegistry` — logs the dispatch.
    """

    OPERATOR_NAME = "Tm"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
