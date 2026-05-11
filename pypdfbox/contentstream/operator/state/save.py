"""``q`` — Save the graphics state.

Mirrors ``org.apache.pdfbox.contentstream.operator.state.Save`` (PDFBox 3.x;
Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/state/Save.java``).
"""

from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator, OperatorName
from ..operator_processor import OperatorProcessor


class Save(OperatorProcessor):
    """``q`` — push the current graphics-state frame onto the stack."""

    OPERATOR_NAME = OperatorName.SAVE

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        del operator, operands
        context = self._context
        if context is not None:
            context.save_graphics_state()

    def get_name(self) -> str:
        return OperatorName.SAVE


__all__ = ["Save"]
