from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from .graphics_operator_processor import GraphicsOperatorProcessor


class EndPath(GraphicsOperatorProcessor):
    """``n`` — End the path object without filling or stroking it.
    Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.EndPath``
    (upstream lines 32–50).

    Used primarily to set a clipping region. The path-painting
    pipeline arrives with the rendering cluster.
    """

    OPERATOR_NAME = OperatorName.ENDPATH

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)

    def get_name(self) -> str:
        return OperatorName.ENDPATH


__all__ = ["EndPath"]
