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

    Lite stub: registry-routing scaffold only. The constructed-image
    type now exists as
    :class:`pypdfbox.pdmodel.graphics.image.PDInlineImage` (which
    consumes the ``ID`` byte payload via its constructor), but full
    BI/ID/EI dispatch through the engine lands with the rendering
    cluster's engine wiring in a later wave.
    """

    OPERATOR_NAME = "ID"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
