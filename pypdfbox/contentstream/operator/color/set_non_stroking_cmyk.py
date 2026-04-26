from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetNonStrokingCMYK(OperatorProcessor):
    """``k`` — Set the non-stroking colour space to ``DeviceCMYK`` and
    the non-stroking colour. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceCMYKColor``.

    Lite stub: registry-routing scaffold only — the colour-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "k"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
