"""``rg`` — Set the non-stroking color space to DeviceRGB and set the color.

Mirrors ``org.apache.pdfbox.contentstream.operator.color.SetNonStrokingDeviceRGBColor``
(PDFBox 3.x; Java path
``pdfbox/src/main/java/org/apache/pdfbox/contentstream/operator/color/SetNonStrokingDeviceRGBColor.java``).
"""

from __future__ import annotations

from typing import Any

from pypdfbox.cos import COSBase, COSName

from .. import Operator, OperatorName
from .set_non_stroking_color import SetNonStrokingColor


class SetNonStrokingDeviceRGBColor(SetNonStrokingColor):
    """``rg`` — switch the non-stroking color space to DeviceRGB, then sc."""

    OPERATOR_NAME = OperatorName.NON_STROKING_RGB

    def process(self, operator: Operator, operands: list[COSBase]) -> None:
        context = self._context
        if context is not None and not context.is_should_process_color_operators():
            return
        if context is not None:
            resources = context.get_resources()
            if resources is not None:
                get_cs = getattr(resources, "get_color_space", None)
                cs = get_cs(COSName.get_pdf_name("DeviceRGB")) if get_cs else None
                graphics_state = context.get_graphics_state()
                set_cs = getattr(graphics_state, "set_non_stroking_color_space", None)
                if set_cs is not None and cs is not None:
                    set_cs(cs)
        super().process(operator, operands)

    def get_name(self) -> str:
        return OperatorName.NON_STROKING_RGB

    def get_color_space(self) -> Any | None:
        try:
            from pypdfbox.pdmodel.graphics.color import PDDeviceRGB

            return PDDeviceRGB.INSTANCE
        except ImportError:
            return super().get_color_space()


__all__ = ["SetNonStrokingDeviceRGBColor"]
