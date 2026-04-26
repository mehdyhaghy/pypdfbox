from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetStrokingCMYK(OperatorProcessor):
    """``K`` — Set the stroking colour space to ``DeviceCMYK`` and the
    stroking colour. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceCMYKColor``.

    Lite stub: registry-routing scaffold only — the colour-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "K"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
