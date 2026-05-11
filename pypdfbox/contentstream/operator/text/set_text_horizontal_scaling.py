"""``Tz`` — Set horizontal text scaling.

Mirrors ``org.apache.pdfbox.contentstream.operator.text.SetTextHorizontalScaling``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/text/SetTextHorizontalScaling.java``).
"""

from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator, OperatorName
from ..operator_processor import OperatorProcessor


class SetTextHorizontalScaling(OperatorProcessor):
    """``Tz`` — set the horizontal text scaling on the graphics-state
    text state."""

    OPERATOR_NAME = OperatorName.SET_TEXT_HORIZONTAL_SCALING

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        base = operands[0]
        if not isinstance(base, COSNumber):
            return
        context = self._context
        if context is None:
            return
        graphics_state = context.get_graphics_state()
        text_state = getattr(graphics_state, "get_text_state", None)
        text = text_state() if text_state is not None else None
        if text is None:
            return
        setter = getattr(text, "set_horizontal_scaling", None)
        if setter is not None:
            setter(base.float_value())

    def get_name(self) -> str:
        return OperatorName.SET_TEXT_HORIZONTAL_SCALING


__all__ = ["SetTextHorizontalScaling"]
