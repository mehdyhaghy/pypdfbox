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
        neg_ty = -ty.float_value()
        # Upstream re-enters the engine via processOperator(TL, ...). We
        # mirror that when a TL handler is registered so listeners see
        # the synthetic op. Otherwise fall through to a direct engine
        # notification so subclasses still observe the leading change
        # without needing to register a TL handler. Always exactly ONE
        # leading notification fires (preventing the prior double-fire
        # when both paths were active).
        if OperatorName.SET_TEXT_LEADING in ctx.get_operators():
            ctx.process_operator(
                OperatorName.SET_TEXT_LEADING,
                [COSFloat(neg_ty)],
            )
        else:
            ctx.set_text_leading(neg_ty)
        ctx.process_operator(OperatorName.MOVE_TEXT, list(operands))

    def get_name(self) -> str:
        return OperatorName.MOVE_TEXT_SET_LEADING
