from __future__ import annotations

from pypdfbox.cos import COSBase, COSFloat, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class MoveTextSetLeading(OperatorProcessor):
    """``TD`` — Move text position and set leading. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.MoveTextSetLeading``.

    Operand shape: ``tx ty TD``. Equivalent to ``-ty TL`` followed by
    ``tx ty Td`` — we delegate to the engine's processor for both,
    matching upstream's decomposition.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        ty = operands[1]
        if not isinstance(ty, COSNumber):
            return
        ctx = self.get_context()
        # Direct engine notification so subclasses can hook leading even
        # when no SET_TEXT_LEADING handler is registered.
        ctx.set_text_leading(-ty.float_value())
        # Surface a synthetic ``TL`` op when a handler is registered,
        # matching upstream's processOperator(SET_TEXT_LEADING, ...) call.
        if OperatorName.SET_TEXT_LEADING in ctx.get_operators():
            ctx.process_operator(
                OperatorName.SET_TEXT_LEADING,
                [COSFloat(-ty.float_value())],
            )
        ctx.process_operator(OperatorName.MOVE_TEXT, list(operands))

    def get_name(self) -> str:
        return OperatorName.MOVE_TEXT_SET_LEADING
