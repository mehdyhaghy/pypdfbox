from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber
from pypdfbox.pdmodel.graphics.state import RenderingMode

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class SetTextRenderingMode(OperatorProcessor):
    """``Tr`` — Set the text rendering mode. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetTextRenderingMode``.

    Operand shape: ``mode Tr``. Single integer operand 0..7 per
    ISO 32000-1 §9.3.6 (0=fill, 1=stroke, 2=fill+stroke, 3=invisible,
    4=fill+clip, 5=stroke+clip, 6=fill+stroke+clip, 7=clip). Engine-
    coupled handler: dispatches via the engine's
    ``set_text_rendering_mode`` notification when present, otherwise
    no-ops — cluster #2's base engine doesn't track text state, matching
    the upstream PDFBox 4.x base-engine behaviour.

    A missing operand raises :class:`MissingOperandException`; a wrong-
    typed operand is silently dropped.

    Filename suffixed with ``_op`` to avoid colliding with the pre-
    existing ``set_text_rendering_mode.py`` lite-stub module routed via
    :class:`OperatorRegistry`.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        mode = operands[0]
        if not isinstance(mode, COSNumber):
            return
        value = mode.int_value()
        if value < 0 or value >= len(RenderingMode):
            return
        ctx = self.get_context()
        notifier = getattr(ctx, "set_text_rendering_mode", None)
        if callable(notifier):
            notifier(value)

    def get_name(self) -> str:
        return OperatorName.SET_TEXT_RENDERINGMODE
