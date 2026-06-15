from __future__ import annotations

from pypdfbox.cos import COSBase, COSName
from pypdfbox.pdmodel.graphics.state.rendering_intent import RenderingIntent

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class SetRenderingIntent(OperatorProcessor):
    """``ri`` — Set the colour rendering intent in the graphics state.
    Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetRenderingIntent``.

    Operand validation matches upstream:

    * Empty operand list raises :class:`MissingOperandException`.
    * If the first operand is not a :class:`COSName`, the operator is
      silently skipped (upstream ``return``s after the ``instanceof``
      check). Unlike the numeric line-state operators, ``ri`` only
      inspects ``operands[0]`` — extra trailing operands are ignored.

    Upstream then resolves the name through
    :meth:`RenderingIntent.from_string` (unknown names fall back to
    ``RelativeColorimetric``) and stores it on the current graphics
    state.
    """

    OPERATOR_NAME = "ri"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        first = operands[0]
        if not isinstance(first, COSName):
            return
        context = self.get_context()
        if context is None:
            self._log_invocation(operator, operands)
            return
        graphics_state = context.get_graphics_state()
        if graphics_state is None:
            return
        set_rendering_intent = getattr(
            graphics_state, "set_rendering_intent", None
        )
        if callable(set_rendering_intent):
            set_rendering_intent(RenderingIntent.from_string(first.get_name()))

    @staticmethod
    def get_intent_name(operands: list[COSBase]) -> COSName | None:
        """Typed accessor — return the leading :class:`COSName` rendering
        intent key from ``operands``, or ``None`` when the operand list
        is empty or the first operand is not a name. Mirrors upstream's
        leading-``instanceof COSName`` extraction pattern. Does *not*
        raise on a malformed operand list — matches the upstream
        silent-skip behaviour."""
        if not operands:
            return None
        first = operands[0]
        if not isinstance(first, COSName):
            return None
        return first
