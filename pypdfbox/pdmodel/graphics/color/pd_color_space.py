from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSBase

if TYPE_CHECKING:
    from .pd_color import PDColor


class PDColorSpace(ABC):
    """A color space specifies how the colours of graphics objects will be
    painted on the page. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace``.

    Lite surface: factory ``create()``, image conversion (``to_rgb``,
    ``to_rgb_image``, ``to_raw_image``), default decode arrays, and the AWT
    helpers are deferred until the rendering module lands.
    """

    def __init__(self, array: COSArray | None = None) -> None:
        # Subclasses defined by an array form (e.g. ICCBased, Indexed, Lab,
        # CalGray, CalRGB, DeviceN, Separation, Pattern) populate ``array``.
        # Device color spaces leave it as ``None`` and override
        # ``get_cos_object``.
        self._array = array

    @staticmethod
    def create(base: COSBase | None) -> PDColorSpace | None:
        from pypdfbox.cos import COSName

        from .pd_cal_gray import PDCalGray
        from .pd_cal_rgb import PDCalRGB
        from .pd_device_cmyk import PDDeviceCMYK
        from .pd_device_gray import PDDeviceGray
        from .pd_device_n import PDDeviceN
        from .pd_device_rgb import PDDeviceRGB
        from .pd_icc_based import PDICCBased
        from .pd_indexed import PDIndexed
        from .pd_lab import PDLab
        from .pd_pattern import PDPattern
        from .pd_separation import PDSeparation

        if base is None:
            return None
        name: str | None = None
        array: COSArray | None = None
        if isinstance(base, COSName):
            name = base.get_name()
        elif isinstance(base, COSArray) and base.size() > 0:
            head = base.get_object(0)
            if isinstance(head, COSName):
                name = head.get_name()
                array = base
        if name in ("DeviceGray", "G"):
            return PDDeviceGray.INSTANCE
        if name in ("DeviceRGB", "RGB"):
            return PDDeviceRGB.INSTANCE
        if name in ("DeviceCMYK", "CMYK"):
            return PDDeviceCMYK.INSTANCE
        if name == "Pattern":
            return PDPattern()
        if array is not None:
            if name in ("Indexed", "I"):
                return PDIndexed(array)
            if name == "Separation":
                return PDSeparation(array)
            if name == "DeviceN":
                return PDDeviceN(array)
            if name == "ICCBased":
                return PDICCBased(array)
            if name == "CalGray":
                return PDCalGray(array)
            if name == "CalRGB":
                return PDCalRGB(array)
            if name == "Lab":
                return PDLab(array)
        return None

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSBase | None:
        return self._array

    @property
    def name(self) -> str:
        """Compatibility alias for callers that need the COS color-space name."""
        return self.get_name()

    # ---------- abstract surface ----------

    @abstractmethod
    def get_name(self) -> str:
        """Return the name of the color space (e.g. ``"DeviceGray"``)."""

    @abstractmethod
    def get_number_of_components(self) -> int:
        """Return the number of color components in this color space."""

    @abstractmethod
    def get_initial_color(self) -> PDColor:
        """Return the initial (default) color value for this color space."""

    def __str__(self) -> str:
        return self.get_name()


__all__ = ["PDColorSpace"]
