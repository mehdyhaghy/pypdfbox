from __future__ import annotations

from pypdfbox.cos import COSArray, COSBase

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class ShowTextAdjusted(OperatorProcessor):
    """``TJ`` — Show one or more text strings with positioning. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowTextAdjusted``.

    Operand shape: ``[ <string> <number> <string> ... ] TJ``. Numbers
    inside the array are glyph-space x adjustments (negative shifts
    glyphs to the right). Cluster #2 forwards the raw array to
    :meth:`PDFStreamEngine.show_text_strings`.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        array = operands[0]
        if not isinstance(array, COSArray):
            return
        self.get_context().show_text_strings(array)

    def get_name(self) -> str:
        return OperatorName.SHOW_TEXT_ADJUSTED
