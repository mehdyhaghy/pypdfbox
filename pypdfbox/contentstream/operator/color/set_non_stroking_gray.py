from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetNonStrokingGray(OperatorProcessor):
    """``g`` — Set the non-stroking colour space to ``DeviceGray`` and
    the non-stroking colour. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceGrayColor``.

    Lite stub: registry-routing scaffold only — the colour-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "g"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
