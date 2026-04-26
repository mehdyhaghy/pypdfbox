from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetGraphicsStateParameters(OperatorProcessor):
    """``gs`` — Apply the parameters of the named ExtGState dictionary
    to the current graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetGraphicsStateParameters``.

    Lite stub: registry-routing scaffold only — ExtGState resolution
    lands with the rendering-prep cluster.
    """

    OPERATOR_NAME = "gs"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
