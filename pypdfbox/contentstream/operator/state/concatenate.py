"""``cm`` — Concatenate matrix to current transformation matrix.

Mirrors ``org.apache.pdfbox.contentstream.operator.state.Concatenate``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Concatenate.java``).

Functional logic already lives in
:class:`pypdfbox.contentstream.operator.graphics.concatenate_matrix.ConcatenateMatrix`;
this class is the upstream-named parity surface that delegates to that
handler so PDFBox developers can reach for the familiar identifier.
"""

from __future__ import annotations

from typing import cast

from pypdfbox.cos import COSBase, COSNumber

from .. import MissingOperandException, Operator, OperatorName
from ..operator_processor import OperatorProcessor


class Concatenate(OperatorProcessor):
    """``cm`` — pop six numeric operands and concatenate them as a 3×3
    affine matrix onto the current CTM."""

    OPERATOR_NAME = OperatorName.CONCAT

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if len(operands) < 6:
            raise MissingOperandException(operator, operands)
        if not self.check_array_types_class(operands[:6], COSNumber):
            return
        numbers = cast("list[COSNumber]", operands[:6])
        matrix = tuple(number.float_value() for number in numbers)
        context = self._context
        if context is not None:
            # Prefer the dedicated transform hook (mirrors the
            # ConcatenateMatrix handler); fall back to nudging the
            # graphics-state CTM directly to match upstream semantics
            # for engines that don't expose ``transform``.
            transform = getattr(context, "transform", None)
            if transform is not None:
                transform(matrix)
                return
            graphics_state = context.get_graphics_state()
            ctm = getattr(graphics_state, "get_current_transformation_matrix", None)
            ctm_obj = ctm() if ctm is not None else None
            concat = getattr(ctm_obj, "concatenate", None) if ctm_obj else None
            if concat is not None:
                # Upstream calls ``CTM.concatenate(matrix)`` with a Matrix,
                # not the raw six floats; ``Matrix.concatenate`` reads
                # ``matrix._single`` and would crash on a plain tuple.
                from pypdfbox.util.matrix import Matrix  # noqa: PLC0415

                concat(Matrix(*matrix))

    def get_name(self) -> str:
        return OperatorName.CONCAT


__all__ = ["Concatenate"]
