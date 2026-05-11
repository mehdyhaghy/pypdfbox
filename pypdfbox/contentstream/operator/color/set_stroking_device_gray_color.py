"""``G`` — Set the stroking color space to DeviceGray and set the gray level.

Mirrors ``org.apache.pdfbox.contentstream.operator.color.SetStrokingDeviceGrayColor``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetStrokingDeviceGrayColor.java``).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSBase, COSName

from .. import Operator, OperatorName
from .set_stroking_color import SetStrokingColor


class SetStrokingDeviceGrayColor(SetStrokingColor):
    """``G`` — switch the stroking color space to DeviceGray, then SC."""

    OPERATOR_NAME = OperatorName.STROKING_COLOR_GRAY

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        context = self._context
        if context is not None and not context.is_should_process_color_operators():
            return
        if context is not None:
            resources = context.get_resources()
            if resources is not None:
                get_cs = getattr(resources, "get_color_space", None)
                cs = get_cs(COSName.get_pdf_name("DeviceGray")) if get_cs else None
                graphics_state = context.get_graphics_state()
                set_cs = getattr(graphics_state, "set_stroking_color_space", None)
                if set_cs is not None and cs is not None:
                    set_cs(cs)
        super().process(operator, operands)

    def get_name(self) -> str:
        return OperatorName.STROKING_COLOR_GRAY

    def get_color_space(self) -> Any | None:
        try:
            from pypdfbox.pdmodel.graphics.color import PDDeviceGray

            return PDDeviceGray.INSTANCE
        except ImportError:
            return super().get_color_space()


__all__ = ["SetStrokingDeviceGrayColor"]
