from __future__ import annotations

from typing import ClassVar

from .pd_color import PDColor
from .pd_device_color_space import PDDeviceColorSpace


class PDDeviceRGB(PDDeviceColorSpace):
    """Colours in the DeviceRGB colour space are specified according to the
    additive RGB (red-green-blue) colour model. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceRGB``. Use the
    singleton ``PDDeviceRGB.INSTANCE``."""

    INSTANCE: ClassVar[PDDeviceRGB]

    def __init__(self) -> None:
        super().__init__()
        self._initial_color = PDColor([0.0, 0.0, 0.0], self)

    def get_name(self) -> str:
        return "DeviceRGB"

    def get_number_of_components(self) -> int:
        return 3

    def get_initial_color(self) -> PDColor:
        return self._initial_color


PDDeviceRGB.INSTANCE = PDDeviceRGB()


__all__ = ["PDDeviceRGB"]
