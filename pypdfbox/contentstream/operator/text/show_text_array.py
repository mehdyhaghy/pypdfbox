from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class ShowTextArray(OperatorProcessor):
    """``TJ`` — Show one or more text strings with positioning. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowTextAdjusted``.

    Lite stub used by :class:`OperatorRegistry` — logs the dispatch.
    """

    OPERATOR_NAME = "TJ"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
