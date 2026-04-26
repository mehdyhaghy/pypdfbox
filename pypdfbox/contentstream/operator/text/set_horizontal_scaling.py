from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetHorizontalScaling(OperatorProcessor):
    """``Tz`` — Set the horizontal text scaling. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetHorizontalTextScaling``.

    Lite stub: registry-routing scaffold only — the text-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "Tz"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
