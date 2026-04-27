from __future__ import annotations

from pypdfbox.cos import COSBase, COSNumber

from .. import (
    MissingOperandException,
    Operator,
    OperatorName,
    OperatorProcessor,
)


class SetHorizontalTextScaling(OperatorProcessor):
    """``Tz`` — Set the horizontal text scaling factor. Mirrors
    ``org.apache.pdfbox.contentstream.operator.text.SetHorizontalTextScaling``.

    Operand shape: ``scale Tz``. Single ``COSNumber`` operand expressed
    in *percent* per ISO 32000-1 §9.3.4 (e.g. ``100`` for 1.0). Engine-
    coupled handler: forwards via the engine's ``set_horizontal_scaling``
    notification when the engine exposes one (cluster #3+ rendering
    subclass), otherwise no-ops — cluster #2's base engine doesn't track
    text state, matching the upstream PDFBox 4.x base-engine behaviour.

    A missing operand raises :class:`MissingOperandException`; a wrong-
    typed operand is silently dropped.
    """

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        if not operands:
            raise MissingOperandException(operator, operands)
        scale = operands[0]
        if not isinstance(scale, COSNumber):
            return
        ctx = self.get_context()
        # Cluster #2's base engine doesn't track horizontal scaling;
        # subclasses that do override ``set_horizontal_scaling``.
        notifier = getattr(ctx, "set_horizontal_scaling", None)
        if callable(notifier):
            notifier(scale.float_value())

    def get_name(self) -> str:
        return OperatorName.SET_TEXT_HORIZONTAL_SCALING
