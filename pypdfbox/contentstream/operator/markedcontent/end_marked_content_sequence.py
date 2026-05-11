"""``EMC`` — Ends a marked-content sequence begun by ``BMC`` or ``BDC``.

Mirrors ``org.apache.pdfbox.contentstream.operator.markedcontent.EndMarkedContentSequence``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/EndMarkedContentSequence.java``).
"""

from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName, OperatorProcessor


class EndMarkedContentSequence(OperatorProcessor):
    """``EMC`` — close the current marked-content sequence."""

    OPERATOR_NAME = OperatorName.END_MARKED_CONTENT

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator, operands
        context = self._context
        if context is None:
            return
        hook = getattr(context, "end_marked_content_sequence", None)
        if hook is not None:
            hook()

    def get_name(self) -> str:
        return OperatorName.END_MARKED_CONTENT


__all__ = ["EndMarkedContentSequence"]
