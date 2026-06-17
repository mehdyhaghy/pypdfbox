from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor
from ._device_color import PDDeviceCMYK, set_device_color


class SetStrokingCMYK(OperatorProcessor):
    """``K`` — Set the stroking colour space to ``DeviceCMYK`` and the
    stroking colour. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceCMYKColor``.

    When bound to an engine, forwards a ``PDColor`` in the
    ``DeviceCMYK`` color space to ``set_stroking_color``. Malformed
    operand lists are skipped.
    """

    OPERATOR_NAME = "K"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        set_device_color(
            self._context,
            operands,
            color_space=PDDeviceCMYK.INSTANCE,
            component_count=4,
            stroking=True,
            operator=operator,
        )
