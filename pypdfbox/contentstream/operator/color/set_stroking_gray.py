from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor
from ._device_color import PDDeviceGray, set_device_color


class SetStrokingGray(OperatorProcessor):
    """``G`` — Set the stroking colour space to ``DeviceGray`` and the
    stroking colour. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceGrayColor``.

    When bound to an engine, forwards a ``PDColor`` in the
    ``DeviceGray`` color space to ``set_stroking_color``. Malformed
    operand lists are skipped.
    """

    OPERATOR_NAME = "G"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        set_device_color(
            self._context,
            operands,
            color_space=PDDeviceGray.INSTANCE,
            component_count=1,
            stroking=True,
            operator=operator,
        )
