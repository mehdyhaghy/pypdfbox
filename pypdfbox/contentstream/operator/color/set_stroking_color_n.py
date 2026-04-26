from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetStrokingColorN(OperatorProcessor):
    """``SCN`` — Same as ``SC`` but also supports Pattern, Separation,
    DeviceN and ICCBased colour spaces. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetStrokingColorN``.

    Lite stub: registry-routing scaffold only — the colour-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "SCN"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
