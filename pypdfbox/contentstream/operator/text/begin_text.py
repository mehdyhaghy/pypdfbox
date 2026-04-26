from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName, OperatorProcessor


class BeginText(OperatorProcessor):
    """``BT`` — Begin a text object. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.BeginText``.

    Resets the text matrix and text-line matrix to identity, then
    notifies the engine via :meth:`PDFStreamEngine.begin_text`. Cluster
    #2 represents the identity matrix as a 6-element list ``[1, 0, 0, 1,
    0, 0]`` — the text-state cluster will swap this for the real
    ``Matrix`` class.
    """

    _IDENTITY: list[float] = [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        ctx = self.get_context()
        ctx.set_text_matrix(list(self._IDENTITY))
        ctx.set_text_line_matrix(list(self._IDENTITY))
        ctx.begin_text()

    def get_name(self) -> str:
        return OperatorName.BEGIN_TEXT
