from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSBase, COSNumber
from pypdfbox.pdmodel.graphics.color import (
    PDColor,
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)

if TYPE_CHECKING:
    from pypdfbox.contentstream.pdf_stream_engine import PDFStreamEngine
    from pypdfbox.pdmodel.graphics.color import PDColorSpace


def set_device_color(
    engine: PDFStreamEngine | None,
    operands: list[COSBase],
    *,
    color_space: PDColorSpace,
    component_count: int,
    stroking: bool,
) -> None:
    """Build a device-space ``PDColor`` and notify the engine hook.

    Malformed streams are tolerated by skipping the operator, matching
    the existing contentstream operator policy in this package.
    """
    if (
        engine is None
        or not engine.is_should_process_color_operators()
        or len(operands) < component_count
    ):
        return
    components: list[float] = []
    for operand in operands[:component_count]:
        if not isinstance(operand, COSNumber):
            return
        components.append(operand.float_value())
    color = PDColor(components, color_space)
    if stroking:
        engine.set_stroking_color(color)
    else:
        engine.set_non_stroking_color(color)


__all__ = [
    "PDDeviceCMYK",
    "PDDeviceGray",
    "PDDeviceRGB",
    "set_device_color",
]
