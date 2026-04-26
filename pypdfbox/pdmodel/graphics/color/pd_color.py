from __future__ import annotations

from typing import TYPE_CHECKING

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName

if TYPE_CHECKING:
    from .pd_color_space import PDColorSpace


def _clamp_unit(value: float) -> float:
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def _clamp_rgb(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    r, g, b = rgb
    return (_clamp_unit(r), _clamp_unit(g), _clamp_unit(b))


class PDColor:
    """A color value, consisting of one or more color components, or for
    pattern color spaces, a name and optional color components. Mirrors
    PDFBox ``org.apache.pdfbox.pdmodel.graphics.color.PDColor``.

    Lite surface: ``to_rgb()`` covers the common device + CIE color
    spaces (DeviceGray/RGB/CMYK, Indexed with a DeviceRGB base, Lab via
    D65 + sRGB matrix). Pattern, ICCBased, DeviceN and Separation raise
    ``NotImplementedError`` until rendering lands.
    """

    def __init__(
        self,
        components: list[float],
        color_space: PDColorSpace,
        pattern: COSName | None = None,
    ) -> None:
        # Defensive copy to keep the instance immutable from the outside.
        self._components: list[float] = [float(c) for c in components]
        self._color_space = color_space
        self._pattern_name = pattern

    # ---------- accessors ----------

    def get_components(self) -> list[float]:
        return list(self._components)

    def get_color_space(self) -> PDColorSpace:
        return self._color_space

    def get_pattern_name(self) -> COSName | None:
        return self._pattern_name

    def is_pattern(self) -> bool:
        return self._pattern_name is not None

    # ---------- conversion ----------

    def to_rgb(self) -> tuple[float, float, float]:
        """Return this color converted to sRGB as a tuple of three
        floats clamped to ``[0.0, 1.0]``.

        Dispatches on the color space name per PDF 32000-1 §8.6.4. Lite
        surface: ``CalGray`` and ``CalRGB`` short-circuit to their
        device equivalents (no gamma/matrix applied), ``Indexed``
        assumes a DeviceRGB base and 1 byte per component, and ``Lab``
        uses a fixed D65 white point with the sRGB matrix and gamma
        encoding (no chromatic adaptation, no black-point compensation).
        ``Pattern``, ``ICCBased``, ``DeviceN`` and ``Separation`` raise
        :class:`NotImplementedError`.
        """
        name = self._color_space.get_name()
        if name == "DeviceGray":
            g = _clamp_unit(self._components[0])
            return (g, g, g)
        if name == "DeviceRGB":
            return _clamp_rgb(
                (self._components[0], self._components[1], self._components[2])
            )
        if name == "DeviceCMYK":
            c, m, y, k = (
                self._components[0],
                self._components[1],
                self._components[2],
                self._components[3],
            )
            r = (1.0 - c) * (1.0 - k)
            g = (1.0 - m) * (1.0 - k)
            b = (1.0 - y) * (1.0 - k)
            return _clamp_rgb((r, g, b))
        if name == "Indexed":
            return self._indexed_to_rgb()
        if name == "CalGray":
            # Lite: treat as DeviceGray (no gamma/white-point applied).
            g = _clamp_unit(self._components[0])
            return (g, g, g)
        if name == "CalRGB":
            # Lite: treat as DeviceRGB (no gamma/matrix applied).
            return _clamp_rgb(
                (self._components[0], self._components[1], self._components[2])
            )
        if name == "Lab":
            return self._lab_to_rgb()
        if name in ("Pattern", "ICCBased", "DeviceN", "Separation"):
            raise NotImplementedError(
                f"PDColor.to_rgb() is not implemented for color space {name!r}"
            )
        raise NotImplementedError(
            f"PDColor.to_rgb() is not implemented for color space {name!r}"
        )

    # --- helpers for to_rgb ---

    def _indexed_to_rgb(self) -> tuple[float, float, float]:
        # Lite: assume DeviceRGB base, 1 byte per component, palette as
        # raw bytes. components[0] is the palette index (0..hival).
        cs = self._color_space
        index = int(self._components[0])
        if index < 0:
            index = 0
        get_lookup = getattr(cs, "get_lookup_data", None)
        if get_lookup is None:
            raise NotImplementedError(
                "Indexed color space lacks get_lookup_data()"
            )
        lookup = get_lookup()
        if not lookup:
            raise NotImplementedError(
                "Indexed color space has no lookup table"
            )
        offset = index * 3
        if offset + 2 >= len(lookup):
            # clamp to last entry to stay defensive
            offset = max(0, len(lookup) - 3)
        r = lookup[offset] / 255.0
        g = lookup[offset + 1] / 255.0
        b = lookup[offset + 2] / 255.0
        return _clamp_rgb((r, g, b))

    def _lab_to_rgb(self) -> tuple[float, float, float]:
        # Standard Lab -> XYZ (D65) -> linear sRGB -> sRGB gamma.
        # PDF spec §8.6.5.4. No chromatic adaptation, fixed D65 reference.
        l_star, a_star, b_star = (
            self._components[0],
            self._components[1],
            self._components[2],
        )

        # CIE Lab -> XYZ with D65 white point (X_n, Y_n, Z_n).
        x_n, y_n, z_n = 0.95047, 1.0, 1.08883

        fy = (l_star + 16.0) / 116.0
        fx = fy + a_star / 500.0
        fz = fy - b_star / 200.0

        # Inverse of the f() function used in CIE Lab.
        delta = 6.0 / 29.0

        def _finv(t: float) -> float:
            if t > delta:
                return t * t * t
            return 3.0 * delta * delta * (t - 4.0 / 29.0)

        x = x_n * _finv(fx)
        y = y_n * _finv(fy)
        z = z_n * _finv(fz)

        # Linear sRGB from XYZ (D65 -> sRGB matrix, IEC 61966-2-1).
        r_lin = 3.2404542 * x - 1.5371385 * y - 0.4985314 * z
        g_lin = -0.9692660 * x + 1.8760108 * y + 0.0415560 * z
        b_lin = 0.0556434 * x - 0.2040259 * y + 1.0572252 * z

        def _srgb_encode(u: float) -> float:
            if u <= 0.0031308:
                return 12.92 * u
            return 1.055 * (u ** (1.0 / 2.4)) - 0.055

        return _clamp_rgb(
            (_srgb_encode(r_lin), _srgb_encode(g_lin), _srgb_encode(b_lin))
        )

    # ---------- COS surface ----------

    def to_cos_array(self) -> COSArray:
        array = COSArray()
        for component in self._components:
            array.add(COSFloat(component))
        if self._pattern_name is not None:
            array.add(self._pattern_name)
        return array

    @classmethod
    def from_cos_array(
        cls,
        array: COSArray,
        color_space: PDColorSpace,
    ) -> PDColor:
        components: list[float] = []
        pattern: COSName | None = None
        for index in range(array.size()):
            item = array.get_object(index)
            if isinstance(item, (COSFloat, COSInteger)):
                components.append(float(item.value))
            elif isinstance(item, COSName):
                pattern = item
        return cls(components, color_space, pattern)


__all__ = ["PDColor"]
