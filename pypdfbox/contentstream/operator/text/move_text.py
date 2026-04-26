from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class MoveText(OperatorProcessor):
    """``Td`` — Move text position by ``(tx, ty)``. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.MoveText``.

    Operand shape: ``tx ty Td``. Translates the text-line matrix and
    copies the result back to the text matrix.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        tx = operands[0]
        ty = operands[1]
        if not isinstance(tx, COSNumber) or not isinstance(ty, COSNumber):
            return
        self.get_context().move_text_position(tx.float_value(), ty.float_value())

    def get_name(self) -> str:
        return OperatorName.MOVE_TEXT
