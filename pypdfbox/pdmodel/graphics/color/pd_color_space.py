from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resources import PDResources

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
    def create(
        base: COSBase | None,
        resources: PDResources | None = None,
    ) -> PDColorSpace | None:
        """Build a typed ``PDColorSpace`` from its COS form.

        Mirrors upstream ``PDColorSpace.create(COSBase, PDResources)``:

        - ``None`` → ``None``.
        - ``COSObject`` is unwrapped to its referenced object first.
        - ``COSName`` for a *device* color space (long form
          ``DeviceGray``/``DeviceRGB``/``DeviceCMYK`` or the inline-image
          short form ``G``/``RGB``/``CMYK``) → device singleton.
        - ``COSName == "Pattern"`` → colored Pattern color space.
        - any other ``COSName``: looked up in
          ``resources.get_color_space(name)`` when ``resources`` is
          supplied; ``None`` otherwise. This is the standard way named
          color spaces flow from a page's ``/Resources/ColorSpace``
          entry to a typed object.
        - ``COSArray`` whose first element is a known color-space name
          (``Indexed``/``I``, ``Separation``, ``DeviceN``, ``ICCBased``,
          ``CalGray``, ``CalRGB``, ``Lab``, ``Pattern``) → the matching
          array-form color space.

        ``resources`` is keyword-only-ish (positional for upstream
        parity); pass ``None`` for the common case where the dispatch is
        purely structural and no name resolution is needed.
        """
        from pypdfbox.cos import COSName
        from pypdfbox.cos.cos_object import COSObject

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

        # Unwrap indirect references — upstream calls
        # ``COSObject.getObject()`` before the type dispatch.
        if isinstance(base, COSObject):
            base = base.get_object()
            if base is None:
                return None

        if isinstance(base, COSName):
            cs_name = base.get_name()
            if cs_name in ("DeviceGray", "G"):
                return PDDeviceGray.INSTANCE
            if cs_name in ("DeviceRGB", "RGB"):
                return PDDeviceRGB.INSTANCE
            if cs_name in ("DeviceCMYK", "CMYK"):
                return PDDeviceCMYK.INSTANCE
            if cs_name == "Pattern":
                return PDPattern(resources=resources)
            # Any other name must be resolved through the page's
            # /Resources/ColorSpace dictionary.
            if resources is not None:
                return resources.get_color_space(base)
            return None

        if isinstance(base, COSArray) and base.size() > 0:
            head = base.get_object(0)
            if not isinstance(head, COSName):
                return None
            arr_name = head.get_name()
            if arr_name in ("DeviceGray", "G"):
                return PDDeviceGray.INSTANCE
            if arr_name in ("DeviceRGB", "RGB"):
                return PDDeviceRGB.INSTANCE
            if arr_name in ("DeviceCMYK", "CMYK"):
                return PDDeviceCMYK.INSTANCE
            if arr_name in ("Indexed", "I"):
                return PDIndexed(base)
            if arr_name == "Separation":
                return PDSeparation(base)
            if arr_name == "DeviceN":
                return PDDeviceN(base)
            if arr_name == "ICCBased":
                return PDICCBased(base)
            if arr_name == "CalGray":
                return PDCalGray(base)
            if arr_name == "CalRGB":
                return PDCalRGB(base)
            if arr_name == "Lab":
                return PDLab(base)
            if arr_name == "Pattern":
                # [/Pattern <underlying CS>] — uncolored tiling.
                underlying: PDColorSpace | None = None
                if base.size() > 1:
                    underlying = PDColorSpace.create(
                        base.get_object(1), resources
                    )
                return PDPattern(underlying, resources=resources)
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
