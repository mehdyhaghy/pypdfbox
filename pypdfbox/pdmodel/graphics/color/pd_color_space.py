from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase, COSDictionary, COSName

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_resources import PDResources

    from .pd_color import PDColor


class PDColorSpace(ABC):
    """A color space specifies how the colours of graphics objects will be
    painted on the page. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDColorSpace``.

    Lite surface: factory ``create()``, default decode arrays, best-effort
    raster conversion (``to_rgb_image`` / ``to_raw_image``), and structural
    predicates. Java AWT helpers are compatibility stubs because there is no
    Python equivalent.
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
        was_default: bool = False,
        _seen_color_space_dicts: set[int] | None = None,
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

        The ``was_default`` flag mirrors upstream's internal-use
        ``create(COSBase, PDResources, boolean)`` overload — set when
        the call is already resolving a ``DefaultGray`` /
        ``DefaultRGB`` / ``DefaultCMYK`` mapping. In pypdfbox the
        actual default-color-space lookup happens inside
        :meth:`PDResources.get_color_space`, so this flag is
        propagated through recursive ``create()`` calls (e.g. when
        unwrapping a PDFBOX-4833 dictionary) but does not itself
        trigger a default lookup here.

        A ``COSDictionary`` whose ``/ColorSpace`` entry references a
        valid color-space form is unwrapped (PDFBOX-4833). A
        ``/ColorSpace`` entry that points back to its containing
        dictionary, directly or through another wrapper dictionary
        (PDFBOX-5315), raises :class:`OSError`.
        """
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

        # PDFBOX-4833: a dictionary with a /ColorSpace entry — unwrap it.
        if isinstance(base, COSDictionary) and base.contains_key(
            COSName.get_pdf_name("ColorSpace")
        ):
            if _seen_color_space_dicts is None:
                _seen_color_space_dicts = set()
            dictionary_id = id(base)
            if dictionary_id in _seen_color_space_dicts:
                raise OSError(
                    "Recursion in colorspace: /ColorSpace chain loops"
                )
            _seen_color_space_dicts.add(dictionary_id)
            inner = base.get_dictionary_object(
                COSName.get_pdf_name("ColorSpace")
            )
            # PDFBOX-5315: a /ColorSpace entry that points back at its
            # containing dictionary is a self-recursion — bail out
            # rather than spin into infinite recursion.
            if inner is base:
                raise OSError(
                    "Recursion in colorspace: /ColorSpace points to itself"
                )
            return PDColorSpace.create(
                inner, resources, was_default, _seen_color_space_dicts
            )
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

        Default behaviour matches the spec's general rule: ``[0, 1]``
        repeated per component. Concrete subclasses override for the
        spaces that differ (``DeviceCMYK``, ``Indexed``, ``Lab``).
        """
        n = self.get_number_of_components()
        out: list[float] = []
        for _ in range(n):
            out.append(0.0)
            out.append(1.0)
        return out

    # ---------- rendering ----------

    def to_rgb_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Convert a raster of 8-bits-per-component color values in this
        color space into an sRGB Pillow ``Image``. Mirrors upstream
        ``PDColorSpace.toRGBImage(WritableRaster)``.

        ``raster`` is interpreted as a tightly-packed buffer of
        ``width * height * get_number_of_components()`` bytes. Each
        sample is mapped through this color space's default decode array
        (so Indexed bytes stay integer indices, while Device* / Lab /
        ICCBased samples land in the ``[0, 1]`` / Lab range expected by
        :meth:`PDColor.to_rgb`).
        """
        from PIL import Image

        from .pd_color import PDColor

        n = self.get_number_of_components()
        if n <= 0:
            raise ValueError(
                f"Cannot rasterise {self.get_name()!r} with {n} components"
            )
        expected = int(width) * int(height) * n
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))
        # /Decode maps each 8-bit sample [0, 255] -> [low_c, high_c].
        decode = self.get_default_decode(8)
        if len(decode) < 2 * n:
            # Fall back to [0, 1] per component if the override returned
            # something narrower than the spec mandates.
            decode = []
            for _ in range(n):
                decode.extend([0.0, 1.0])
        out = bytearray(int(width) * int(height) * 3)
        for pixel_index in range(int(width) * int(height)):
            offset = pixel_index * n
            components = []
            for c in range(n):
                low = decode[2 * c]
                high = decode[2 * c + 1]
                sample = data[offset + c] / 255.0
                components.append(low + sample * (high - low))
            r, g, b = PDColor(components, self).to_rgb()
            base = pixel_index * 3
            out[base] = max(0, min(255, int(round(r * 255.0))))
            out[base + 1] = max(0, min(255, int(round(g * 255.0))))
            out[base + 2] = max(0, min(255, int(round(b * 255.0))))
        return Image.frombytes("RGB", (int(width), int(height)), bytes(out))

    def to_raw_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Return the raster as a Pillow ``Image`` in its native color
        space when it has a Pillow analogue (``DeviceGray`` → ``L``,
        ``DeviceRGB`` → ``RGB``, ``DeviceCMYK`` → ``CMYK``); falls
        through to :meth:`to_rgb_image` for any other space (Lab,
        Indexed, ICCBased, Cal*, Separation, DeviceN, Pattern). Mirrors
        upstream ``PDColorSpace.toRawImage(WritableRaster)``.
        """
        from PIL import Image

        name = self.get_name()
        n = self.get_number_of_components()
        if name in ("DeviceGray", "G") and n == 1:
            return Image.frombytes(
                "L", (int(width), int(height)), bytes(raster)
            )
        if name in ("DeviceRGB", "RGB") and n == 3:
            return Image.frombytes(
                "RGB", (int(width), int(height)), bytes(raster)
            )
        if name in ("DeviceCMYK", "CMYK") and n == 4:
            return Image.frombytes(
                "CMYK", (int(width), int(height)), bytes(raster)
            )
        return self.to_rgb_image(raster, width, height)

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
