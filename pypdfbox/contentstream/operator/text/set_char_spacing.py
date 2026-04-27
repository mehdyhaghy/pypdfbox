from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class SetCharSpacing(OperatorProcessor):
    """``Tc`` — Set the character spacing. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetCharSpacing``.

    Operand shape: ``charSpacing Tc``. Single ``COSNumber`` operand.
    Engine-coupled handler: forwards the spacing to
    :meth:`PDFStreamEngine.set_character_spacing`. A missing operand
    raises :class:`MissingOperandException`; a wrong-typed operand is
    silently dropped (matching upstream's ``instanceof COSNumber``
    short-circuit).
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        spacing = operands[0]
        if not isinstance(spacing, COSNumber):
            return
        self.get_context().set_character_spacing(spacing.float_value())

    def get_name(self) -> str:
        return OperatorName.SET_CHAR_SPACING
