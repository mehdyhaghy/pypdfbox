"""``MP`` — Define a marked-content point.

Mirrors ``org.apache.pdfbox.contentstream.operator.markedcontent.MarkedContentPoint``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/MarkedContentPoint.java``).
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import MissingOperandException, Operator, OperatorName, OperatorProcessor


class MarkedContentPoint(OperatorProcessor):
    """``MP`` — flag a single point in the content stream as a marked
    content point (no associated property dictionary)."""

    OPERATOR_NAME = OperatorName.MARKED_CONTENT_POINT

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSName):
            return
        context = self._context
        if context is None:
            return
        hook = getattr(context, "marked_content_point", None)
        if hook is not None:
            hook(operands[0], None)

    def get_name(self) -> str:
        return OperatorName.MARKED_CONTENT_POINT


__all__ = ["MarkedContentPoint"]
