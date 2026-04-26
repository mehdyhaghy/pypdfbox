from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetStrokingColorSpace(OperatorProcessor):
    """``CS`` — Set the current colour space to use for stroking
    operations. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetStrokingColorSpace``.

    Lite stub: registry-routing scaffold only — the colour-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "CS"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
