from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

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

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Return the default ``/Decode`` array for image XObjects in this
        color space (PDF 32000-1 §8.9.5.1, Table 90).

        Base implementation raises :class:`NotImplementedError`; concrete
        subclasses override (for most spaces this is ``[0, 1]`` repeated
        per component, but ``DeviceCMYK``, ``Indexed`` and ``Lab`` differ).
        """
        raise NotImplementedError(
            f"get_default_decode is not implemented for {self.get_name()!r}"
        )

    # ---------- rendering (deferred) ----------

    def to_rgb_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Convert a raster of color values in this color space into an
        sRGB image. Mirrors upstream
        ``PDColorSpace.toRGBImage(WritableRaster)``.

        Deferred until the rendering module lands — concrete pixel
        conversion belongs alongside the Pillow-based renderer.
        """
        raise NotImplementedError(
            f"to_rgb_image is not implemented for {self.get_name()!r} "
            "(rendering module deferred)"
        )

    def to_raw_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Return the raster as an image in its native color space, with
        no sRGB conversion. Mirrors upstream
        ``PDColorSpace.toRawImage(WritableRaster)``.

        Deferred until the rendering module lands.
        """
        raise NotImplementedError(
            f"to_raw_image is not implemented for {self.get_name()!r} "
            "(rendering module deferred)"
        )

    def get_java_color_space(self) -> Any:
        """Return the underlying ``java.awt.color.ColorSpace`` instance.

        Java-AWT-specific upstream API: there is no Python equivalent in
        this port, so this always returns ``None``. Kept for surface
        compatibility with PDFBox callers.
        """
        return None

    # ---------- type predicates ----------

    def is_pattern(self) -> bool:
        """Return ``True`` if this is a Pattern color space."""
        from .pd_pattern import PDPattern

        return isinstance(self, PDPattern)

    def is_indexed(self) -> bool:
        """Return ``True`` if this is an Indexed color space."""
        from .pd_indexed import PDIndexed

        return isinstance(self, PDIndexed)

    def is_separation(self) -> bool:
        """Return ``True`` if this is a Separation color space."""
        from .pd_separation import PDSeparation

        return isinstance(self, PDSeparation)

    def is_device_n(self) -> bool:
        """Return ``True`` if this is a DeviceN color space."""
        from .pd_device_n import PDDeviceN

        return isinstance(self, PDDeviceN)

    # ---------- array form ----------

    def get_array(self) -> COSArray | None:
        """Return the underlying ``COSArray`` when this color space was
        constructed in array form (e.g. ``[/ICCBased <stream>]``,
        ``[/Indexed ...]``); ``None`` for name-only device color spaces.
        """
        return self._array

    def __str__(self) -> str:
        return self.get_name()


__all__ = ["PDColorSpace"]
