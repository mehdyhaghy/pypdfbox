from __future__ import annotations

from typing import ClassVar

from .pd_color import PDColor
from .pd_device_color_space import PDDeviceColorSpace


class PDDeviceGray(PDDeviceColorSpace):
    """A color space with black, white, and intermediate shades of gray.
    Mirrors PDFBox ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceGray``.
    Use the singleton ``PDDeviceGray.INSTANCE``."""

    INSTANCE: ClassVar[PDDeviceGray]

    def __init__(self) -> None:
        super().__init__()
        self._initial_color = PDColor([0.0], self)

    def get_name(self) -> str:
        return "DeviceGray"

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> PDColor:
        return self._initial_color


PDDeviceGray.INSTANCE = PDDeviceGray()


__all__ = ["PDDeviceGray"]
