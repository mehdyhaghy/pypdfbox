"""``d`` — Set the line dash pattern.

Mirrors ``org.apache.pdfbox.contentstream.operator.state.SetLineDashPattern``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/SetLineDashPattern.java``).
"""

from __future__ import annotations

import logging

from pypdfbox.cos import COSArray, COSBase, COSNumber

from .. import MissingOperandException, Operator, OperatorName
from ..operator_processor import OperatorProcessor

_log = logging.getLogger(__name__)


class SetLineDashPattern(OperatorProcessor):
    """``d`` — replace the dash pattern + phase on the graphics state.

    Operand shape: ``<array> <phase> d`` where ``<array>`` is the dash
    pattern (alternating on / off lengths) and ``<phase>`` is the
    starting offset.
    """

    OPERATOR_NAME = OperatorName.SET_LINE_DASHPATTERN

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        base0 = operands[0]
        if not isinstance(base0, COSArray):
            return
        base1 = operands[1]
        if not isinstance(base1, COSNumber):
            return
        dash_array: COSArray = base0
        dash_phase = base1.int_value()

        # Mirror the upstream sanity check: if every entry compares
        # equal to 0 (or any entry isn't a number), upstream replaces
        # the whole pattern with an empty array. The loop short-circuits
        # at the first non-zero numeric entry — matching upstream's
        # ``Float.compare`` break-on-first-non-zero semantic.
        for entry in dash_array:
            if isinstance(entry, COSNumber):
                if entry.float_value() != 0:
                    break
            else:
                _log.warning(
                    "dash array has non number element %r, ignored", entry
                )
                dash_array = COSArray()
                break

        context = self._context
        if context is not None:
            setter = getattr(context, "set_line_dash_pattern", None)
            if setter is not None:
                setter(dash_array, dash_phase)

    def get_name(self) -> str:
        return OperatorName.SET_LINE_DASHPATTERN


__all__ = ["SetLineDashPattern"]
