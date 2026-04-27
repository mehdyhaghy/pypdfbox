from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class SetTextRise(OperatorProcessor):
    """``Ts`` — Set the text rise. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetTextRise``.

    Operand shape: ``rise Ts``. Single ``COSNumber`` operand expressed
    in unscaled text-space units per ISO 32000-1 §9.3.7. Engine-coupled
    handler: dispatches via the engine's ``set_text_rise`` notification
    when present, otherwise no-ops — cluster #2's base engine doesn't
    track text state.

    A missing operand raises :class:`MissingOperandException`; a wrong-
    typed operand is silently dropped.

    Filename suffixed with ``_op`` to avoid colliding with the pre-
    existing ``set_text_rise.py`` lite-stub module routed via
    :class:`OperatorRegistry`.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        rise = operands[0]
        if not isinstance(rise, COSNumber):
            return
        ctx = self.get_context()
        notifier = getattr(ctx, "set_text_rise", None)
        if callable(notifier):
            notifier(rise.float_value())

    def get_name(self) -> str:
        return OperatorName.SET_TEXT_RISE
