from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SaveGraphicsState(OperatorProcessor):
    """``q`` — Save the current graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.Save``.

    Lite stub: registry-routing scaffold only. The actual graphics-
    state stack push lands with the rendering-prep cluster — for now
    this just logs the dispatch.
    """

    OPERATOR_NAME = "q"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
