from __future__ import annotations

from pypdfbox.cos import COSBase, COSString

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class ShowText(OperatorProcessor):
    """``Tj`` — Show a text string. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowText``.

    Operand shape: ``<string> Tj``. Upstream silently no-ops when
    operands are empty or the entry isn't a ``COSString``; pypdfbox
    raises :class:`MissingOperandException` when zero operands are
    supplied (a strictly more conservative shape — empty operand stack
    is always a stream-level bug, and the operator-exception machinery
    in :meth:`PDFStreamEngine.operator_exception` demotes it to a log
    line so behaviour at the engine level matches upstream).
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        text = operands[0]
        if not isinstance(text, COSString):
            return
        ctx = self.get_context()
        # Upstream guards on ``getTextMatrix() == null`` to skip Tj that
        # land outside a BT/ET pair. Cluster #2's default returns ``None``
        # always, so applying that guard here would refuse every show.
        # We defer the guard to subclasses that override
        # ``get_text_matrix`` with real text-state tracking (cluster #3+).
        ctx.show_text_string(text.get_bytes())

    def get_name(self) -> str:
        return OperatorName.SHOW_TEXT
