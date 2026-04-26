from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class ShowTextWithPosition(OperatorProcessor):
    """``'`` (apostrophe) — Move to next line and show text. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowTextLine``.

    Lite stub used by :class:`OperatorRegistry` — logs the dispatch.
    """

    OPERATOR_NAME = "'"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
