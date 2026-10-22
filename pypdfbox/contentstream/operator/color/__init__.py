"""Color-state operator handlers.

Mirrors ``org.apache.pdfbox.contentstream.operator.color``. The package
hosts both the existing functional handlers (``SetStrokingColor``,
``SetNonStrokingColor``, etc.) and the upstream-named parity wrappers
(``SetColor``, ``SetStrokingDeviceCMYKColor``, etc.).
"""

from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .set_color import SetColor
    from .set_non_stroking_color import SetNonStrokingColor
    from .set_non_stroking_color_n import SetNonStrokingColorN
    from .set_non_stroking_color_space import SetNonStrokingColorSpace
    from .set_non_stroking_device_cmyk_color import SetNonStrokingDeviceCMYKColor
    from .set_non_stroking_device_gray_color import SetNonStrokingDeviceGrayColor
    from .set_non_stroking_device_rgb_color import SetNonStrokingDeviceRGBColor
    from .set_stroking_color import SetStrokingColor
    from .set_stroking_color_n import SetStrokingColorN
    from .set_stroking_color_space import SetStrokingColorSpace
    from .set_stroking_device_cmyk_color import SetStrokingDeviceCMYKColor
    from .set_stroking_device_gray_color import SetStrokingDeviceGrayColor
    from .set_stroking_device_rgb_color import SetStrokingDeviceRGBColor

__getattr__, __dir__ = _attach(
    __name__,
    {
        "SetColor": ".set_color",
        "SetNonStrokingColor": ".set_non_stroking_color",
        "SetNonStrokingColorN": ".set_non_stroking_color_n",
        "SetNonStrokingColorSpace": ".set_non_stroking_color_space",
        "SetNonStrokingDeviceCMYKColor": ".set_non_stroking_device_cmyk_color",
        "SetNonStrokingDeviceGrayColor": ".set_non_stroking_device_gray_color",
        "SetNonStrokingDeviceRGBColor": ".set_non_stroking_device_rgb_color",
        "SetStrokingColor": ".set_stroking_color",
        "SetStrokingColorN": ".set_stroking_color_n",
        "SetStrokingColorSpace": ".set_stroking_color_space",
        "SetStrokingDeviceCMYKColor": ".set_stroking_device_cmyk_color",
        "SetStrokingDeviceGrayColor": ".set_stroking_device_gray_color",
        "SetStrokingDeviceRGBColor": ".set_stroking_device_rgb_color",
    },
)

__all__ = [
    "SetColor",
    "SetNonStrokingColor",
    "SetNonStrokingColorN",
    "SetNonStrokingColorSpace",
    "SetNonStrokingDeviceCMYKColor",
    "SetNonStrokingDeviceGrayColor",
    "SetNonStrokingDeviceRGBColor",
    "SetStrokingColor",
    "SetStrokingColorN",
    "SetStrokingColorSpace",
    "SetStrokingDeviceCMYKColor",
    "SetStrokingDeviceGrayColor",
    "SetStrokingDeviceRGBColor",
]
