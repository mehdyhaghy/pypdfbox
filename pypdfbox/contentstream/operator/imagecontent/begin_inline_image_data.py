from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class BeginInlineImageData(OperatorProcessor):
    """``ID`` — Marks the start of the inline image's data stream.
    Mirrors the ``ID`` operator handled in upstream PDFBox by
    ``org.apache.pdfbox.contentstream.operator.BeginInlineImage`` (the
    image-data bytes are read straight off the stream, not driven via a
    separate processor).

    Lite stub kept for registry parity. ``ID`` is never dispatched as
    a standalone operator at the engine level — the parser
    (:class:`pypdfbox.pdfparser.PDFStreamParser`) absorbs the ``ID``
    byte payload into the preceding ``BI`` operator's ``image_data``
    slot, and the engine's ``BI`` interception in
    :meth:`PDFStreamEngine.process_operator` builds the
    :class:`pypdfbox.pdmodel.graphics.image.PDInlineImage` from there.
    The stub still exists so the operator-name registry surface
    matches upstream's ``OperatorRegistry`` listing.
    """

    OPERATOR_NAME = "ID"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
