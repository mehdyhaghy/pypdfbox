from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class SetFlatness(OperatorProcessor):
    """``i`` — Set the flatness tolerance in the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetFlatness``.

    Operand validation matches upstream exactly:

    * Empty operand list raises :class:`MissingOperandException`.
    * ``checkArrayTypesClass(operands, COSNumber)`` over the WHOLE operand
      list — if any operand is non-numeric the operator is silently
      skipped (upstream ``return``s after the guard).
    * Otherwise ``operands[0].float_value()`` is applied to
      ``set_flatness`` (upstream widens the float to a double; pypdfbox
      stores a plain float — value-equal for the operand range).
    """

    OPERATOR_NAME = "i"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands, COSNumber):
            return
        first = operands[0]
        if not isinstance(first, COSNumber):
            return
        context = self.get_context()
        if context is None:
            self._log_invocation(operator, operands)
            return
        graphics_state = context.get_graphics_state()
        if graphics_state is None:
            return
        set_flatness = getattr(graphics_state, "set_flatness", None)
        if callable(set_flatness):
            set_flatness(first.float_value())
