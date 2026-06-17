from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor
from ._device_color import PDDeviceRGB, set_device_color


class SetStrokingRGB(OperatorProcessor):
    """``RG`` — Set the stroking colour space to ``DeviceRGB`` and the
    stroking colour. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceRGBColor``.

    When bound to an engine, forwards a ``PDColor`` in the
    ``DeviceRGB`` color space to ``set_stroking_color``. Malformed
    operand lists are skipped.
    """

    OPERATOR_NAME = "RG"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        set_device_color(
            self._context,
            operands,
            color_space=PDDeviceRGB.INSTANCE,
            component_count=3,
            stroking=True,
            operator=operator,
        )
