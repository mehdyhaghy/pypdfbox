from typing import TYPE_CHECKING

from pypdfbox._lazy_exports import attach as _attach

if TYPE_CHECKING:
    from .pd_cal_gray import PDCalGray
    from .pd_cal_rgb import PDCalRGB
    from .pd_cie_based_color_space import PDCIEBasedColorSpace
    from .pd_cie_dictionary_based_color_space import PDCIEDictionaryBasedColorSpace
    from .pd_color import PDColor
    from .pd_color_space import PDColorSpace
    from .pd_device_cmyk import PDDeviceCMYK
    from .pd_device_color_space import PDDeviceColorSpace
    from .pd_device_gray import PDDeviceGray
    from .pd_device_n import PDDeviceN
    from .pd_device_rgb import PDDeviceRGB
    from .pd_gamma import PDGamma
    from .pd_icc_based import PDICCBased
    from .pd_indexed import PDIndexed
    from .pd_jpx_color_space import PDJPXColorSpace
    from .pd_lab import PDLab
    from .pd_output_intent import PDOutputIntent
    from .pd_pattern import PDPattern
    from .pd_separation import PDSeparation
    from .pd_special_color_space import PDSpecialColorSpace
    from .pd_tristimulus import PDTristimulus

__getattr__, __dir__ = _attach(
    __name__,
    {
        "PDCalGray": ".pd_cal_gray",
        "PDCalRGB": ".pd_cal_rgb",
        "PDCIEBasedColorSpace": ".pd_cie_based_color_space",
        "PDCIEDictionaryBasedColorSpace": ".pd_cie_dictionary_based_color_space",
        "PDColor": ".pd_color",
        "PDColorSpace": ".pd_color_space",
        "PDDeviceCMYK": ".pd_device_cmyk",
        "PDDeviceColorSpace": ".pd_device_color_space",
        "PDDeviceGray": ".pd_device_gray",
        "PDDeviceN": ".pd_device_n",
        "PDDeviceRGB": ".pd_device_rgb",
        "PDGamma": ".pd_gamma",
        "PDICCBased": ".pd_icc_based",
        "PDIndexed": ".pd_indexed",
        "PDJPXColorSpace": ".pd_jpx_color_space",
        "PDLab": ".pd_lab",
        "PDOutputIntent": ".pd_output_intent",
        "PDPattern": ".pd_pattern",
        "PDSeparation": ".pd_separation",
        "PDSpecialColorSpace": ".pd_special_color_space",
        "PDTristimulus": ".pd_tristimulus",
    },
)

__all__ = [
    "PDCalGray",
    "PDCalRGB",
    "PDCIEBasedColorSpace",
    "PDCIEDictionaryBasedColorSpace",
    "PDColor",
    "PDColorSpace",
    "PDDeviceCMYK",
    "PDDeviceColorSpace",
    "PDDeviceGray",
    "PDDeviceN",
    "PDDeviceRGB",
    "PDGamma",
    "PDICCBased",
    "PDIndexed",
    "PDJPXColorSpace",
    "PDLab",
    "PDOutputIntent",
    "PDPattern",
    "PDSeparation",
    "PDSpecialColorSpace",
    "PDTristimulus",
]
