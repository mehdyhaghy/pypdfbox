from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class EndInlineImage(OperatorProcessor):
    """``EI`` — End an inline image object. Mirrors the ``EI`` operator
    closure in
    ``org.apache.pdfbox.contentstream.operator.BeginInlineImage``.

    Lite stub: registry-routing scaffold only — inline-image decoding
    arrives with the rendering cluster; for now this just logs the
    dispatch.
    """

    OPERATOR_NAME = "EI"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
