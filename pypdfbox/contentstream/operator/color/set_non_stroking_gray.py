from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor
from ._device_color import PDDeviceGray, set_device_color


class SetNonStrokingGray(OperatorProcessor):
    """``g`` — Set the non-stroking colour space to ``DeviceGray`` and
    the non-stroking colour. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceGrayColor``.

    When bound to an engine, forwards a ``PDColor`` in the
    ``DeviceGray`` color space to ``set_non_stroking_color``. Malformed
    operand lists are skipped.
    """

    OPERATOR_NAME = "g"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        set_device_color(
            self._context,
            operands,
            color_space=PDDeviceGray.INSTANCE,
            component_count=1,
            stroking=False,
            operator=operator,
        )
