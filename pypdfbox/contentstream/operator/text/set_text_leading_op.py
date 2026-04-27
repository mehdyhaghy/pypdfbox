from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class SetTextLeading(OperatorProcessor):
    """``TL`` — Set the text leading. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetTextLeading``.

    Operand shape: ``leading TL``. Single ``COSNumber`` operand.
    Engine-coupled handler: forwards via
    :meth:`PDFStreamEngine.set_text_leading`. A missing operand raises
    :class:`MissingOperandException`; a wrong-typed operand is silently
    dropped.

    Filename suffixed with ``_op`` to avoid colliding with the pre-
    existing ``set_text_leading.py`` lite-stub module routed via
    :class:`OperatorRegistry`.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        leading = operands[0]
        if not isinstance(leading, COSNumber):
            return
        self.get_context().set_text_leading(leading.float_value())

    def get_name(self) -> str:
        return OperatorName.SET_TEXT_LEADING
