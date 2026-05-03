from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SaveGraphicsState(OperatorProcessor):
    """``q`` — Save the current graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.Save``.

    When bound to a :class:`PDFStreamEngine` context, follows upstream
    parity: invokes ``save_graphics_state()`` on the engine so the
    rendering subclass can push the active graphics-state frame onto
    the stack. Standalone (context-less) dispatch falls through to the
    log path so registry-only consumers stay unaffected — the lite
    registry-routing scaffold has no engine to forward to.
    """

    OPERATOR_NAME = "q"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
        context = self._context
        if context is None:
            return
        context.save_graphics_state()
