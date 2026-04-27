from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class EndInlineImage(OperatorProcessor):
    """``EI`` — End an inline image object. Mirrors the ``EI`` operator
    closure in
    ``org.apache.pdfbox.contentstream.operator.BeginInlineImage``.

    Lite stub: registry-routing scaffold only. The construction landing
    point is now
    :class:`pypdfbox.pdmodel.graphics.image.PDInlineImage` (which takes
    ``(parameters, data, resources)`` and runs the filter chain), but
    full ``EI`` dispatch — pulling the BI parameter dictionary and the
    ID byte payload out of the parser's :class:`Operator` and forwarding
    a constructed ``PDInlineImage`` to a
    ``PDFStreamEngine.show_inline_image`` hook — lands together with the
    rendering cluster's engine wiring in a later wave.
    """

    OPERATOR_NAME = "EI"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        # Deferred: build PDInlineImage(operator.image_parameters,
        # operator.image_data, engine.get_resources()) and forward to an
        # engine-level inline-image hook once that hook exists.
        self._log_invocation(operator, operands)
