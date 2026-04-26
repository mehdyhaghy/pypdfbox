from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName, OperatorProcessor


class ShowTextLine(OperatorProcessor):
    """``'`` (apostrophe) — Move to next line and show text. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowTextLine``.

    Operand shape: ``<string> '``. Equivalent to ``T*`` followed by
    ``Tj``. Upstream re-enters the engine via ``processOperator`` for
    each step; we do the same so a subclass that registered just
    :class:`ShowText` (without :class:`ShowTextLine`) still observes
    the underlying ``Tj`` notification.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        ctx = self.get_context()
        ctx.process_operator(OperatorName.NEXT_LINE, None)
        ctx.process_operator(OperatorName.SHOW_TEXT, operands)

    def get_name(self) -> str:
        return OperatorName.SHOW_TEXT_LINE
