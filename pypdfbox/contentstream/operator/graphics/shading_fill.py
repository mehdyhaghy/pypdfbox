from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class ShadingFill(OperatorProcessor):
    """``sh`` — Paint the shape and colour shading described by the
    shading dictionary referenced by the named resource (``/Shading``
    sub-resource on the current page or form XObject). Mirrors
    ``org.apache.pdfbox.contentstream.operator.graphics.ShadingFill``.

    Lite stub: registry-routing scaffold only — looking up the named
    ``/Shading`` resource and dispatching to the shading-type painter
    lands with the rendering cluster.
    """

    OPERATOR_NAME = "sh"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
