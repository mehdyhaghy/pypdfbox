"""``BMC`` — Begin a marked-content sequence.

Mirrors ``org.apache.pdfbox.contentstream.operator.markedcontent.BeginMarkedContentSequence``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/markedcontent/BeginMarkedContentSequence.java``).
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import Operator, OperatorName, OperatorProcessor


class BeginMarkedContentSequence(OperatorProcessor):
    """``BMC`` — pick the last :class:`COSName` from the operand stack and
    forward it to :meth:`PDFStreamEngine.begin_marked_content_sequence`."""

    OPERATOR_NAME = OperatorName.BEGIN_MARKED_CONTENT

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator
        tag: COSName | None = None
        for argument in operands:
            if isinstance(argument, COSName):
                tag = argument
        context = self._context
        if context is None:
            return
        hook = getattr(context, "begin_marked_content_sequence", None)
        if hook is not None:
            hook(tag, None)

    def get_name(self) -> str:
        return OperatorName.BEGIN_MARKED_CONTENT


__all__ = ["BeginMarkedContentSequence"]
