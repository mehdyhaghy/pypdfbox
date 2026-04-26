from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetNonStrokingColorSpace(OperatorProcessor):
    """``cs`` — Set the current colour space to use for non-stroking
    operations. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingColorSpace``.

    Lite stub: registry-routing scaffold only — the colour-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "cs"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
