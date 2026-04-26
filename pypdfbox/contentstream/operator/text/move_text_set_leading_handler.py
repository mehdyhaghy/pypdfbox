from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class MoveTextSetLeading(OperatorProcessor):
    """``TD`` — Move text position and set leading. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.MoveTextSetLeading``.

    Lite stub used by :class:`OperatorRegistry` — logs the dispatch.

    Filename suffixed with ``_handler`` to avoid colliding with the
    pre-existing ``move_text_set_leading.py`` engine-coupled module in
    this package.
    """

    OPERATOR_NAME = "TD"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
