from __future__ import annotations

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
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 6:
            raise MissingOperandException(operator, operands)
        if not all(isinstance(o, COSNumber) for o in operands[:6]):
            return
        matrix = [operands[i].float_value() for i in range(6)]  # type: ignore[union-attr]
        ctx = self.get_context()
        ctx.set_text_matrix(matrix)
        ctx.set_text_line_matrix(list(matrix))

    def get_name(self) -> str:
        return OperatorName.SET_MATRIX
