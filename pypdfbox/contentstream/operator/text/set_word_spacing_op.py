from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class SetWordSpacing(OperatorProcessor):
    """``Tw`` — Set the word spacing. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetWordSpacing``.

    Operand shape: ``wordSpacing Tw``. Single ``COSNumber`` operand.
    Engine-coupled handler: forwards the spacing to
    :meth:`PDFStreamEngine.set_word_spacing`. A missing operand raises
    :class:`MissingOperandException`; a wrong-typed operand is silently
    dropped.

    Filename suffixed with ``_op`` to avoid colliding with the
    pre-existing ``set_word_spacing.py`` lite-stub module routed via
    :class:`OperatorRegistry`.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        spacing = operands[0]
        if not isinstance(spacing, COSNumber):
            return
        self.get_context().set_word_spacing(spacing.float_value())

    def get_name(self) -> str:
        return OperatorName.SET_WORD_SPACING
