from __future__ import annotations

from pypdfbox.cos import COSBase

from .. import Operator
from ..operator_processor import OperatorProcessor
from ._device_color import PDDeviceCMYK, set_device_color


class SetNonStrokingCMYK(OperatorProcessor):
    """``k`` — Set the non-stroking colour space to ``DeviceCMYK`` and
    the non-stroking colour. Mirrors
    ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceCMYKColor``.

    When bound to an engine, forwards a ``PDColor`` in the
    ``DeviceCMYK`` color space to ``set_non_stroking_color``. Malformed
    operand lists are skipped.
    """

    OPERATOR_NAME = "k"

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        set_device_color(
            self._context,
            operands,
            color_space=PDDeviceCMYK.INSTANCE,
            component_count=4,
            stroking=False,
            operator=operator,
        )
