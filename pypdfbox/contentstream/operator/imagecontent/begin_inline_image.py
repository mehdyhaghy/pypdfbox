from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class BeginInlineImage(OperatorProcessor):
    """``BI`` — Begin an inline image object. Mirrors
    ``org.apache.pdfbox.contentstream.operator.BeginInlineImage``.

    Lite stub: registry-routing scaffold only. The constructed-image
    type now exists as
    :class:`pypdfbox.pdmodel.graphics.image.PDInlineImage`, but full
    BI/ID/EI dispatch through the engine lands together with the
    rendering cluster's engine wiring in a later wave.
    """

    OPERATOR_NAME = "BI"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
