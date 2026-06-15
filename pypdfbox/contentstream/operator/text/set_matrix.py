from __future__ import annotations

from typing import cast

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class SetMatrix(OperatorProcessor):
    """``Tm`` — Set the text matrix and text-line matrix. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetMatrix``.

    Operand shape: ``a b c d e f Tm`` — a 3x3 affine matrix in column-
    major form (the bottom row is fixed at ``0 0 1``). Both the text
    matrix and text-line matrix are replaced. Cluster #2 forwards the
    raw 6-element list; the rendering cluster will swap in ``Matrix``.

    Edge cases (parity with upstream
    ``org.apache.pdfbox.contentstream.operator.state.SetMatrix``):

    * Fewer than six operands raises :class:`MissingOperandException`.
    * The type guard mirrors upstream's
      ``checkArrayTypesClass(operands, COSNumber.class)``, which inspects
      the **entire** operand list — not just the first six. So a
      malformed ``a b c d e f <extra> Tm`` with a non-number trailing
      operand is silently dropped (no matrix update), matching upstream;
      only the first six numbers are consumed when every operand is a
      number.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 6:
            raise MissingOperandException(operator, operands)
        # Upstream guards on the WHOLE operand list via
        # ``checkArrayTypesClass(operands, COSNumber.class)``; a trailing
        # non-number operand makes the operator a silent no-op even though
        # the first six are valid numbers.
        if not self.check_array_types_class(operands, COSNumber):
            return
        numbers = cast("list[COSNumber]", operands[:6])
        matrix = [number.float_value() for number in numbers]
        ctx = self.get_context()
        ctx.set_text_matrix(matrix)
        ctx.set_text_line_matrix(list(matrix))

    def get_name(self) -> str:
        return OperatorName.SET_MATRIX
