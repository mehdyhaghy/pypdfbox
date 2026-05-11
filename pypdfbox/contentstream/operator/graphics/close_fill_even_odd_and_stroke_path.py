from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class CloseFillEvenOddAndStrokePath(GraphicsOperatorProcessor):
    """``b*`` — Close, fill, and stroke the path with the even-odd
    winding rule. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.CloseFillEvenOddAndStrokePath``
    (upstream lines 33–53).

    Upstream implementation dispatches two operators through the
    engine: ``CLOSE_PATH`` followed by ``FILL_EVEN_ODD_AND_STROKE``.
    The lite scaffold keeps the same dispatch shape conditioned on the
    presence of a bound engine.
    """

    OPERATOR_NAME = OperatorName.CLOSE_FILL_EVEN_ODD_AND_STROKE

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        ctx = self._context
        if ctx is not None and hasattr(ctx, "process_operator"):
            ctx.process_operator(OperatorName.CLOSE_PATH, operands)
            ctx.process_operator(
                OperatorName.FILL_EVEN_ODD_AND_STROKE, operands
            )
            return
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.CLOSE_FILL_EVEN_ODD_AND_STROKE


__all__ = ["CloseFillEvenOddAndStrokePath"]
