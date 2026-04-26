from __future__ import annotations

from pypdfbox.cos import COSBase, COSName, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class SetFontAndSize(OperatorProcessor):
    """``Tf`` — Set text font and size. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetFontAndSize``.

    Operand shape: ``<font-name> <size> Tf``. Raises
    :class:`MissingOperandException` if fewer than two operands are
    supplied; type-mismatched operands are dropped silently (matching
    upstream's ``instanceof`` short-circuits).
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        font_name = operands[0]
        font_size = operands[1]
        if not isinstance(font_name, COSName):
            return
        if not isinstance(font_size, COSNumber):
            return
        self.get_context().set_font(font_name, font_size.float_value())

    def get_name(self) -> str:
        return OperatorName.SET_FONT_AND_SIZE
