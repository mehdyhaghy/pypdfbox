from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class ClipEvenOddRule(GraphicsOperatorProcessor):
    """``W*`` — Set the clipping path using the even-odd rule. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.ClipEvenOddRule``
    (upstream lines 33–51).

    Lite implementation: the operator carries no operands; the actual
    intersection of the current clipping path with the current path
    using ``Path2D.WIND_EVEN_ODD`` arrives with the rendering cluster.
    """

    OPERATOR_NAME = OperatorName.CLIP_EVEN_ODD

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.CLIP_EVEN_ODD


__all__ = ["ClipEvenOddRule"]
