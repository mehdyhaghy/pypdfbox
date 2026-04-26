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

    # ---------- COS surface ----------

    def get_cos_object(self) -> COSBase | None:
        return self._array

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
