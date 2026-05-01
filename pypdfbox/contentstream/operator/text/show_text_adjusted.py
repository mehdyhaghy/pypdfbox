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

    Upstream silently no-ops when operands are empty or the entry isn't
    a ``COSArray``; pypdfbox raises :class:`MissingOperandException` on
    zero operands (a strictly more conservative shape — empty operand
    stack is always a stream-level bug, and the operator-exception
    machinery in :meth:`PDFStreamEngine.operator_exception` demotes it
    to a log line so behaviour at the engine level matches upstream).

    Upstream additionally guards on ``getTextMatrix() == null`` to skip
    ``TJ`` that lands outside a BT/ET pair. Cluster #2's default returns
    ``None`` always, so applying that guard here would refuse every
    show. We defer the guard to subclasses that override
    :meth:`PDFStreamEngine.get_text_matrix` with real text-state
    tracking (cluster #3+), mirroring the same deferral made in
    :class:`ShowText`.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        array = operands[0]
        if not isinstance(array, COSArray):
            return
        # See class docstring re: the deferred ``get_text_matrix is None``
        # guard — symmetric with :class:`ShowText`.
        self.get_context().show_text_strings(array)

    def get_name(self) -> str:
        return OperatorName.SHOW_TEXT_ADJUSTED
