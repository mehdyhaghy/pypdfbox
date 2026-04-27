from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor


class BeginInlineImage(OperatorProcessor):
    """``BI`` — Begin an inline image object. Mirrors
    ``org.apache.pdfbox.contentstream.operator.BeginInlineImage``.

    Registry-routing scaffold (lite stub). The semantic dispatch lives
    in :meth:`PDFStreamEngine.process_operator`: when a ``BI`` operator
    is seen, the engine builds a
    :class:`pypdfbox.pdmodel.graphics.image.PDInlineImage` from the
    operator's pre-collated ``image_parameters`` + ``image_data`` (set
    by :class:`pypdfbox.pdfparser.PDFStreamParser` when it parses the
    ``BI`` ... ``ID`` ... ``EI`` triplet) and forwards it to
    :meth:`PDFStreamEngine.show_inline_image`. This stub is still
    invoked by the engine after that hook so registry observers
    registered via :meth:`PDFStreamEngine.add_operator` continue to
    receive the operator — matching upstream's ``addOperator
    (BeginInlineImage)`` registration surface.
    """

    OPERATOR_NAME = "BI"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        self._log_invocation(operator, operands)
