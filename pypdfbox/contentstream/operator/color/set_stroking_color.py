from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetStrokingColor(OperatorProcessor):
    """``SC`` — Set the colour to use for stroking operations in a
    device, CIE-based (other than ICCBased), or Indexed colour space.
    Mirrors ``org.apache.pdfbox.contentstream.operator.color.SetStrokingColor``.

    Lite stub: registry-routing scaffold only — the colour-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "SC"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
