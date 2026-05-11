from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class ClipNonZeroRule(GraphicsOperatorProcessor):
    """``W`` — Set the clipping path using the non-zero winding-number
    rule. Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.ClipNonZeroRule``
    (upstream lines 33–51).

    Lite implementation: the operator carries no operands; the actual
    intersection of the current clipping path with the current path
    using ``Path2D.WIND_NON_ZERO`` arrives with the rendering cluster.
    """

    OPERATOR_NAME = OperatorName.CLIP_NON_ZERO

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.CLIP_NON_ZERO


__all__ = ["ClipNonZeroRule"]
