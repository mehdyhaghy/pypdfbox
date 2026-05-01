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

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        return [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]

    def to_rgb(self, value: list[float]) -> list[float]:
        """Convert a single DeviceRGB color value into sRGB. Mirrors
        upstream ``PDDeviceRGB.toRGB(float[])`` — DeviceRGB is the
        identity in pypdfbox's lite color pipeline (no ICC profile
        applied), so the input list is returned unchanged.

        ``value`` must be a list of three floats in ``[0.0, 1.0]``.
        """
        return value


PDDeviceRGB.INSTANCE = PDDeviceRGB()


__all__ = ["PDDeviceRGB"]
