from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class InvokeNamedXObject(OperatorProcessor):
    """``Do`` — Paint the form or image XObject referenced by the named
    resource. Mirrors
    ``org.apache.pdfbox.contentstream.operator.DrawObject``.

    Lite stub: registry-routing scaffold only — XObject resolution and
    painting land with the rendering cluster.
    """

    OPERATOR_NAME = "Do"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
