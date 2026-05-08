from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import Operator
from ..operator_processor import OperatorProcessor


class SetLineWidth(OperatorProcessor):
    """``w`` — Set the line width in the graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineWidth``.

    When bound to an engine with a graphics state, applies the numeric
    width to ``set_line_width``. Malformed operands are skipped, matching
    upstream PDFBox's post-PDFBOX-5861 ``instanceof COSNumber`` guard.
    """

    OPERATOR_NAME = "w"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        width = self.get_line_width(operands)
        if width is None:
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

    @staticmethod
    def get_line_width(operands: list[COSBase]) -> COSNumber | None:
        """Return the leading line-width operand when it is numeric.

        The lite operator keeps the existing short-list tolerance, while
        avoiding the class-cast failure that upstream hardened against
        for malformed content streams.
        """
        if not operands:
            return None
        first = operands[0]
        if not isinstance(first, COSNumber):
            return None
        return first
