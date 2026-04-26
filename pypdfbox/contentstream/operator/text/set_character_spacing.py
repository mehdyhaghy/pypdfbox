from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetCharacterSpacing(OperatorProcessor):
    """``Tc`` — Set the character spacing. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetCharSpacing``.

    Lite stub: registry-routing scaffold only — the text-state
    bookkeeping arrives with the rendering cluster.
    """

    OPERATOR_NAME = "Tc"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
