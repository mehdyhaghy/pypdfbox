from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor
from .empty_graphics_stack_exception import EmptyGraphicsStackException


class RestoreGraphicsState(OperatorProcessor):
    """``Q`` — Restore the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.Restore``.

    Lite stub: registry-routing scaffold only. The actual graphics-
    state stack pop lands with the rendering-prep cluster — for now
    this just logs the dispatch.

    When bound to a :class:`PDFStreamEngine` context, follows upstream
    parity: invokes ``restore_graphics_state()`` only when the engine's
    graphics-state stack has more than one frame; otherwise raises
    :class:`EmptyGraphicsStackException` (mirrors PDFBOX-161 behaviour).
    Standalone (context-less) dispatch falls through to the log path so
    registry-only consumers stay unaffected.
    """

    OPERATOR_NAME = "Q"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
        context = self._context
        if context is None:
            return
        if context.get_graphics_stack_size() > 1:
            context.restore_graphics_state()
        else:
            # this shouldn't happen but it does, see PDFBOX-161
            raise EmptyGraphicsStackException()
