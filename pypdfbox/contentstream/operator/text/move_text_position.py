from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class MoveTextPosition(OperatorProcessor):
    """``Td`` — Move text position by ``(tx, ty)``. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.MoveText``.

    Lite stub used by :class:`OperatorRegistry` — logs the dispatch.
    """

    OPERATOR_NAME = "Td"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
