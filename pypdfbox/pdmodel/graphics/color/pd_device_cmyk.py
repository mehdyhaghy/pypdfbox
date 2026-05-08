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

    Lite surface: ``to_rgb`` uses a simple subtractive approximation.
    ICC-profile-based CMYK conversion remains part of the rendering path.
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

    def to_rgb(self, value: list[float]) -> list[float]:
        """Convert a single DeviceCMYK color value into sRGB. Mirrors
        upstream ``PDDeviceCMYK.toRGB(float[])`` — but until the ICC
        profile pipeline lands, pypdfbox uses the simple subtractive
        approximation ``r = (1-c)(1-k)``, ``g = (1-m)(1-k)``,
        ``b = (1-y)(1-k)``. This matches the formula already used by
        :meth:`PDColor.to_rgb` for DeviceCMYK so the two paths agree.

        ``value`` must be a list of four floats in ``[0.0, 1.0]``.
        """
        c, m, y, k = value[0], value[1], value[2], value[3]
        r = (1.0 - c) * (1.0 - k)
        g = (1.0 - m) * (1.0 - k)
        b = (1.0 - y) * (1.0 - k)
        return [r, g, b]


PDDeviceCMYK.INSTANCE = PDDeviceCMYK()


__all__ = ["PDDeviceCMYK"]
