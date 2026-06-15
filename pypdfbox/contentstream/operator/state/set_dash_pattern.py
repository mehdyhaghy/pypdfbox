from __future__ import annotations

import logging

from pypdfbox.cos import COSArray, COSBase, COSNumber

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor

_log = logging.getLogger(__name__)


class SetDashPattern(OperatorProcessor):
    """``d`` — Set the line dash pattern. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetLineDashPattern``.

    Operand validation matches upstream:

    * Fewer than two operands raises :class:`MissingOperandException`.
    * If the first operand is not a :class:`COSArray`, the operator is
      silently skipped (upstream ``return``s after the ``instanceof``
      check).
    * If the second operand is not a :class:`COSNumber`, the operator
      is silently skipped likewise.

    Upstream additionally inspects the dash array for non-number
    elements and warn-logs / replaces it with an empty (solid) array
    before notifying the stream engine.
    """

    OPERATOR_NAME = "d"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 2:
            raise MissingOperandException(operator, operands)
        dash_array = self.get_dash_array(operands)
        phase = self.get_dash_phase(operands)
        if dash_array is None or phase is None:
            return
        dash_array = self.get_sanitized_dash_array(dash_array)

        context = self.get_context()
        if context is None:
            self._log_invocation(operator, operands)
            return
        context.set_line_dash_pattern(dash_array, phase.int_value())

    @staticmethod
    def get_dash_array(operands: list[COSBase]) -> COSArray | None:
        """Typed accessor — return the leading :class:`COSArray` dash
        array from ``operands``, or ``None`` when ``operands`` is too
        short or the first operand is not an array. Does *not* raise on
        a malformed operand list — matches upstream's silent-skip
        behaviour."""
        if len(operands) < 2:
            return None
        first = operands[0]
        if not isinstance(first, COSArray):
            return None
        return first

    @staticmethod
    def get_dash_phase(operands: list[COSBase]) -> COSNumber | None:
        """Typed accessor — return the trailing :class:`COSNumber` dash
        phase from ``operands``, or ``None`` when ``operands`` is too
        short or either operand has the wrong type. Mirrors upstream's
        ``arguments.get(1)`` access guarded by both ``instanceof``
        checks."""
        if len(operands) < 2:
            return None
        if not isinstance(operands[0], COSArray):
            return None
        second = operands[1]
        if not isinstance(second, COSNumber):
            return None
        return second

    @staticmethod
    def get_sanitized_dash_array(dash_array: COSArray) -> COSArray:
        """Return ``dash_array`` sanitised the way upstream's
        ``SetLineDashPattern`` does.

        Upstream iterates the array and **breaks on the first non-zero
        numeric entry** — only if a *non-number* entry is reached *before*
        any non-zero number does it warn-log and replace the whole array
        with an empty (solid) one. So ``[3 /Bogus]`` keeps its two entries
        (the loop breaks at ``3``), while ``[0 /Bogus]`` and
        ``[/Bogus 3]`` become empty. Mirroring the early-break is required
        for parity: a naive "any non-number → empty" scan diverges on the
        ``[non-zero-number, non-number]`` case.
        """
        for index in range(dash_array.size()):
            entry = dash_array.get_object(index)
            if isinstance(entry, COSNumber):
                if entry.float_value() != 0:
                    break
            else:
                _log.warning(
                    "dash array has non number element %r, ignored", entry
                )
                return COSArray()
        return dash_array
