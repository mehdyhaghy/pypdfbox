from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class SetLineWidth(OperatorProcessor):
    """``w`` — Set the line width in the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineWidth``.

    Operand validation matches upstream exactly:

    * Empty operand list raises :class:`MissingOperandException`.
    * ``checkArrayTypesClass(operands, COSNumber)`` over the WHOLE operand
      list — if any operand is non-numeric the operator is silently
      skipped (upstream ``return``s after the guard). A trailing junk
      operand therefore drops the whole update, matching upstream.
    * Otherwise ``operands[0].float_value()`` is applied to
      ``set_line_width``.
    """

    OPERATOR_NAME = "w"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        width = self.get_line_width(operands)
        if width is None:
            if not operands:
                raise MissingOperandException(operator, operands)
            return
        context = self.get_context()
        if context is None:
            self._log_invocation(operator, operands)
            return
        graphics_state = context.get_graphics_state()
        if graphics_state is None:
            return
        set_line_width = getattr(graphics_state, "set_line_width", None)
        if callable(set_line_width):
            set_line_width(width.float_value())

    def get_line_width(self, operands: list[COSBase]) -> COSNumber | None:
        """Return the leading line-width operand when every operand is
        numeric, else ``None``.

        Mirrors upstream's ``checkArrayTypesClass(operands, COSNumber)``
        guard which inspects the WHOLE operand list (not just the first
        operand) — so a malformed ``5 /Name w`` is silently dropped
        rather than half-applied. Does *not* raise on an empty list; the
        caller handles the ``MissingOperandException`` arity check.
        """
        if not operands:
            return None
        if not self.check_array_types_class(operands, COSNumber):
            return None
        first = operands[0]
        if not isinstance(first, COSNumber):
            return None
        return first
