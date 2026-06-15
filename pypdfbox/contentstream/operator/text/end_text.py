from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName, OperatorProcessor


class EndText(OperatorProcessor):
    """``ET`` — End a text object. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.EndText``.

    Clears the text and text-line matrices, then notifies the engine
    via :meth:`PDFStreamEngine.end_text`.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        ctx = self.get_context()
        # Upstream clears the text-line matrix first, then the text matrix,
        # then notifies the engine. Operand window is ignored (extra
        # operands tolerated; an ``ET`` with no preceding ``BT`` is a no-op
        # clear, never an error).
        ctx.set_text_line_matrix(None)
        ctx.set_text_matrix(None)
        ctx.end_text()

    def get_name(self) -> str:
        return OperatorName.END_TEXT
