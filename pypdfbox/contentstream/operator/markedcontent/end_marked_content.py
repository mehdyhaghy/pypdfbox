from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName, OperatorProcessor


class EndMarkedContent(OperatorProcessor):
    """``EMC`` — End a marked-content sequence begun by ``BMC`` or
    ``BDC``. Mirrors
    ``org.apache.pdfbox.contentstream.operator.markedcontent.EndMarkedContentSequence``.

    Takes no operands. Forwards to the engine's
    :meth:`end_marked_content_sequence` hook when the engine exposes
    one. Mismatched ``EMC`` (no open sequence) is the engine hook's
    concern — :class:`PDFMarkedContentExtractor` silently no-ops in that
    case, matching upstream PDFBox.
    """

    OPERATOR_NAME = OperatorName.END_MARKED_CONTENT  # "EMC"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator, operands  # unused — EMC takes no operands
        context = self._context
        if context is None:
            return
        hook = getattr(context, "end_marked_content_sequence", None)
        if hook is not None:
            hook()

    def get_name(self) -> str:
        return self.OPERATOR_NAME
