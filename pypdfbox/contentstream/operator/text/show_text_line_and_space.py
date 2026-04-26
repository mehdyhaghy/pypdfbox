from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class ShowTextLineAndSpace(OperatorProcessor):
    """``"`` (quotation mark) — Set word & character spacing, move to
    next line, show text. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.ShowTextLineAndSpace``.

    Operand shape: ``<aw> <ac> <string> "``. Decomposes into ``Tw`` /
    ``Tc`` / ``'`` per ISO 32000-1 §9.4.3, dispatched via the engine so
    the constituent processors fire if registered.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 3:
            raise MissingOperandException(operator, operands)
        ctx = self.get_context()
        ctx.process_operator(OperatorName.SET_WORD_SPACING, [operands[0]])
        ctx.process_operator(OperatorName.SET_CHAR_SPACING, [operands[1]])
        ctx.process_operator(OperatorName.SHOW_TEXT_LINE, [operands[2]])

    def get_name(self) -> str:
        return OperatorName.SHOW_TEXT_LINE_AND_SPACE
