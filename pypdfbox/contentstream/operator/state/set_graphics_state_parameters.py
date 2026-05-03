from __future__ import annotations

from pypdfbox.cos import COSBase, COSName

from .. import MissingOperandException, Operator
from ..operator_processor import OperatorProcessor


class SetGraphicsStateParameters(OperatorProcessor):
    """``gs`` — Apply the parameters of the named ExtGState dictionary
    to the current graphics state. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.SetGraphicsStateParameters``.

    Operand validation matches upstream:

    * Empty operand list raises :class:`MissingOperandException`.
    * If the first operand is not a :class:`COSName`, the operator is
      silently skipped (upstream ``return``s after the ``instanceof``
      check).

    Upstream additionally resolves the named ExtGState against the
    current resource dictionary and copies its entries into the
    graphics state; that lookup-and-copy step lands with the
    rendering-prep cluster (no graphics-state object exists yet in the
    lite registry-routing scaffold).
    """

    OPERATOR_NAME = "gs"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        if not isinstance(operands[0], COSName):
            return
        self._log_invocation(operator, operands)

    @staticmethod
    def get_state_name(operands: list[COSBase]) -> COSName | None:
        """Typed accessor — return the leading :class:`COSName` ExtGState
        key from ``operands``, or ``None`` when the operand list is
        empty or the first operand is not a name. Mirrors upstream's
        leading-``instanceof COSName`` extraction pattern in a single
        helper so callers (e.g. inspection tooling) don't have to
        re-implement the guard. Does *not* raise on a malformed operand
        list — matches the upstream silent-skip behaviour."""
        if not operands:
            return None
        first = operands[0]
        if not isinstance(first, COSName):
            return None
        return first
