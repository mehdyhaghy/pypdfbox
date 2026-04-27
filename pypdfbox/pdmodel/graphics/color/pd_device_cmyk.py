from __future__ import annotations

from typing import ClassVar

from .pd_color import PDColor
from .pd_device_color_space import PDDeviceColorSpace


class PDDeviceCMYK(PDDeviceColorSpace):
    """Allows colors to be specified according to the subtractive CMYK
    (cyan, magenta, yellow, black) model typical of printers and other
    paper-based output devices. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDDeviceCMYK``. Use the
    singleton ``PDDeviceCMYK.INSTANCE``.

    Lite surface: ICC-profile-based RGB conversion (``to_rgb`` /
    ``to_rgb_image``) is deferred until rendering lands.
    """

    INSTANCE: ClassVar[PDDeviceCMYK]

    def __init__(self) -> None:
        super().__init__()
        self._initial_color = PDColor([0.0, 0.0, 0.0, 1.0], self)

    def get_name(self) -> str:
        return "DeviceCMYK"

    def get_number_of_components(self) -> int:
        return 4

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        return [0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.0, 1.0]


PDDeviceCMYK.INSTANCE = PDDeviceCMYK()


__all__ = ["PDDeviceCMYK"]
