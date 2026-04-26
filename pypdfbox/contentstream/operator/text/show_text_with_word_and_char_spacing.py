from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class ShowTextWithWordAndCharSpacing(OperatorProcessor):
    """``"`` (quotation mark) — Set word & character spacing, move to
    next line, show text. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowTextLineAndSpace``.

    Lite stub used by :class:`OperatorRegistry` — logs the dispatch.
    """

    OPERATOR_NAME = '"'

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
