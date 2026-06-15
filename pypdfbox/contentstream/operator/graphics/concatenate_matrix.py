from __future__ import annotations

from typing import cast

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class ConcatenateMatrix(OperatorProcessor):
    """``cm`` — Concatenate a matrix to the current transformation
    matrix. Mirrors
    ``org.apache.pdfbox.contentstream.operator.state.Concatenate``.

    Operand shape: ``a b c d e f cm`` — the six numeric components of a
    3x3 affine matrix (column-major; the bottom row is fixed at
    ``0 0 1``). The matrix is concatenated onto the current
    transformation matrix by routing through
    :meth:`PDFStreamEngine.transform`. The base engine's hook is a
    no-op; the rendering subclass overrides it to multiply ``matrix``
    into the active graphics-state CTM.

    Edge cases (parity with upstream):

    * Fewer than six operands raises :class:`MissingOperandException`.
    * Any operand not a :class:`COSNumber` causes a silent skip. Upstream's
      ``Concatenate.process`` calls ``checkArrayTypesClass(arguments,
      COSNumber.class)`` over the **whole** operand list (not just the first
      six), so a malformed ``a b c d e f /Name cm`` (seven operands, trailing
      non-number) is dropped silently rather than applied — matching the same
      whole-list guard ``SetMatrix`` (``Tm``) uses.
    """

    OPERATOR_NAME = OperatorName.CONCAT

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 6:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands, COSNumber):
            return
        numbers = cast("list[COSNumber]", operands[:6])
        matrix = tuple(number.float_value() for number in numbers)
        # Tolerate a standalone (registry-only) processor that has no
        # bound engine — the strict ``OperatorProcessor.get_context``
        # raises in that case, so we read ``_context`` directly to stay
        # compatible with both the lite and strict bases.
        ctx = self._context
        if ctx is not None:
            ctx.transform(matrix)

    def get_name(self) -> str:
        return OperatorName.CONCAT
