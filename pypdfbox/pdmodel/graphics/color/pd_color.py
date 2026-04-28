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
    D65 + sRGB matrix). ``ICCBased`` falls back to its ``/Alternate``
    (or one inferred from ``/N``); ``Separation`` and ``DeviceN``
    evaluate their tint transform via :class:`PDFunction` and forward
    to the alternate; uncolored tiling ``Pattern`` recurses into its
    underlying color space. Colored patterns (no underlying CS) raise
    ``NotImplementedError`` — those need full pattern rendering.
    """

    def __init__(
        self,
        components: list[float] | COSArray,
        arg2: PDColorSpace | COSName,
        arg3: PDColorSpace | COSName | None = None,
        *,
        pattern: COSName | None = None,
    ) -> None:
        """Construct a PDColor. Mirrors the three upstream PDFBox
        constructors (with one historical pypdfbox accommodation):

        - ``PDColor(components, color_space)`` — components-only.
        - ``PDColor(components, pattern_name, color_space)`` — upstream's
          uncolored-tiling form with tint components plus a pattern name.
        - ``PDColor(cos_array, color_space)`` — parses components and an
          optional trailing pattern name out of a ``COSArray`` (the
          serialized form produced by :meth:`to_cos_array`).

        For backward compatibility with the original pypdfbox surface,
        ``PDColor(components, color_space, pattern_name)`` and the
        ``pattern=`` keyword are still accepted; the constructor inspects
        the positional argument types to disambiguate.
        """
        # Variant 3: PDColor(COSArray, PDColorSpace)
        if isinstance(components, COSArray):
            if arg3 is not None or pattern is not None:
                raise TypeError(
                    "PDColor(COSArray, color_space): no third positional or "
                    "pattern= argument allowed when components is a COSArray"
                )
            parsed_components, parsed_pattern = self._parse_cos_array(components)
            self._components = parsed_components
            self._color_space = arg2  # type: ignore[assignment]
            self._pattern_name = parsed_pattern
            return

        # Disambiguate by type — upstream uses (components, name, cs); the
        # original pypdfbox signature was (components, cs, name).
        cs: PDColorSpace
        pattern_name: COSName | None
        if isinstance(arg2, COSName):
            # Upstream: PDColor(components, pattern_name, color_space)
            if arg3 is None or isinstance(arg3, COSName):
                raise TypeError(
                    "PDColor(components, pattern_name, color_space): the "
                    "third positional color_space argument is required"
                )
            cs = arg3
            pattern_name = arg2
        else:
            # Legacy / variant 1: PDColor(components, color_space[, pattern])
            cs = arg2
            if arg3 is not None and not isinstance(arg3, COSName):
                raise TypeError(
                    "PDColor(components, color_space, pattern_name): third "
                    "argument must be a COSName"
                )
            pattern_name = arg3
        if pattern is not None:
            if pattern_name is not None and pattern_name is not pattern:
                raise TypeError(
                    "PDColor: pattern_name passed both positionally and via "
                    "the pattern= keyword"
                )
            pattern_name = pattern

        # Defensive copy to keep the instance immutable from the outside.
        self._components = [float(c) for c in components]
        self._color_space = cs
        self._pattern_name = pattern_name

    # ---------- accessors ----------

    def get_components(self) -> list[float]:
        return list(self._components)

    def set_components(self, values: list[float]) -> None:
        """Replace the color components in place. Upstream ``PDColor`` is
        effectively immutable (constructor-only); we expose this setter
        as a parity hook that re-runs the same defensive copy used by
        ``__init__``.
        """
        self._components = [float(v) for v in values]

    def get_color_space(self) -> PDColorSpace:
        return self._color_space

    def get_color_space_name(self) -> str | None:
        if self._color_space is None:
            return None
        get_name = getattr(self._color_space, "get_name", None)
        if get_name is None:
            return None
        return get_name()

    def get_pattern_name(self) -> COSName | None:
        return self._pattern_name

    def is_pattern(self) -> bool:
        # Upstream test: pattern when color space is a PDPattern. Keep the
        # historical "pattern_name set" trigger too so existing callers
        # constructing a PDColor with just a name still report True.
        if self._pattern_name is not None:
            return True
        cs_name = self.get_color_space_name()
        return cs_name == "Pattern"

    def is_separation(self) -> bool:
        """Return ``True`` if the wrapped color space is a Separation.
        Convenience predicate that delegates to
        :meth:`PDColorSpace.is_separation` — pypdfbox enrichment with no
        upstream PDFBox equivalent on ``PDColor`` (the predicate lives on
        ``PDColorSpace``); we re-expose it here for callers that hold a
        ``PDColor`` and want to branch without poking at the color space.
        """
        if self._color_space is None:
            return False
        is_sep = getattr(self._color_space, "is_separation", None)
        if is_sep is None:
            return False
        return bool(is_sep())

    def is_device_n(self) -> bool:
        """Return ``True`` if the wrapped color space is a DeviceN.
        Convenience predicate that delegates to
        :meth:`PDColorSpace.is_device_n` — pypdfbox enrichment, see
        :meth:`is_separation` for the rationale.
        """
        if self._color_space is None:
            return False
        is_dn = getattr(self._color_space, "is_device_n", None)
        if is_dn is None:
            return False
        return bool(is_dn())

    # ---------- conversion ----------

    def to_rgb(self) -> tuple[float, float, float]:
        """Return this color converted to sRGB as a tuple of three
        floats clamped to ``[0.0, 1.0]``.

        Dispatches on the color space name per PDF 32000-1 §8.6.4. Lite
        surface: ``CalGray`` and ``CalRGB`` short-circuit to their
        device equivalents (no gamma/matrix applied), ``Indexed`` reads
        one byte per base-CS component and converts through the base,
        and ``Lab`` uses a fixed D65 white point with the sRGB matrix
        and gamma encoding (no chromatic adaptation, no black-point
        compensation). ``ICCBased`` evaluates the embedded profile via
        Pillow's ``ImageCms`` when possible and falls back to the
        ``/Alternate`` color space otherwise (or one inferred from
        ``/N``); ``Separation`` and ``DeviceN`` evaluate their tint
        transform and forward to the alternate. Colored ``Pattern``
        instances (no underlying color space) raise
        :class:`NotImplementedError` — pattern shading is a rendering
        concern; uncolored tiling patterns recurse into the underlying
        color space.
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
        # Color spaces that own their own to_rgb logic — delegate.
        if name in ("ICCBased", "Separation", "DeviceN", "Pattern"):
            cs_to_rgb = getattr(self._color_space, "to_rgb", None)
            if cs_to_rgb is None:
                raise NotImplementedError(
                    f"PDColor.to_rgb() is not implemented for color space {name!r}"
                )
            result = cs_to_rgb(self._components)
            if result is None:
                # Colored pattern (no underlying color) — rendering territory.
                raise NotImplementedError(
                    f"PDColor.to_rgb() requires an underlying color space for {name!r}"
                )
            return _clamp_rgb(result)
        raise NotImplementedError(
            f"PDColor.to_rgb() is not implemented for color space {name!r}"
        )

    # --- helpers for to_rgb ---

    def _indexed_to_rgb(self) -> tuple[float, float, float]:
        # Per PDF 32000-1 §8.6.6.3: index components[0] into /Lookup, read
        # one byte per base-CS component, then convert through the base
        # color space. Falls back to DeviceRGB-style 3-byte interpretation
        # when the base CS can't be resolved.
        cs = self._color_space
        index = int(self._components[0])
        if index < 0:
            index = 0
        # Clamp index against /Hival when the CS exposes it.
        get_hival = getattr(cs, "get_hival", None)
        if get_hival is not None:
            try:
                hival = int(get_hival())
                if index > hival:
                    index = hival
            except (TypeError, ValueError):
                pass
        get_lookup = getattr(cs, "get_lookup_data", None)
        if get_lookup is None:
            # No /Lookup accessor — black palette entry is the safest
            # default per upstream's lenient handling.
            return (0.0, 0.0, 0.0)
        lookup = get_lookup()
        if not lookup:
            return (0.0, 0.0, 0.0)
        # Determine base-CS arity. Fall back to 3 (DeviceRGB) when we
        # can't introspect — matches the lite assumption of upstream
        # before its full color-pipeline lands.
        base_cs = None
        get_base = getattr(cs, "get_base_color_space", None)
        if get_base is not None:
            try:
                base_cs = get_base()
            except (TypeError, ValueError):
                base_cs = None
        if base_cs is not None:
            n_components = base_cs.get_number_of_components()
        else:
            n_components = 3
        offset = index * n_components
        if offset + n_components > len(lookup):
            # Clamp to last full entry — defensive parity with upstream's
            # tolerant indexed handling (truncate-or-zero-pad).
            offset = max(0, len(lookup) - n_components)
        # Each lookup byte is in [0, 255] mapping to the base CS's
        # natural range; we normalise to [0, 1] here. For most base
        # color spaces (Device*, Cal*, ICCBased) this matches the
        # /Decode default of [0, 1] and lets the base's to_rgb()
        # consume the components directly.
        components = [
            lookup[offset + i] / 255.0 for i in range(n_components)
        ]
        if base_cs is None:
            # Treat as DeviceRGB (the lite legacy behaviour).
            if len(components) >= 3:
                return _clamp_rgb(
                    (components[0], components[1], components[2])
                )
            if len(components) == 1:
                g = _clamp_unit(components[0])
                return (g, g, g)
            return (0.0, 0.0, 0.0)
        return _clamp_rgb(PDColor(components, base_cs).to_rgb())

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

    def to_rgba(
        self, alpha: float = 1.0
    ) -> tuple[float, float, float, float]:
        """Return this color as ``(r, g, b, a)`` floats clamped to
        ``[0.0, 1.0]``. Convenience over :meth:`to_rgb` — the RGB triple
        is computed via the existing dispatcher and ``alpha`` is appended
        unchanged after a 0..1 range check.

        ``alpha`` defaults to ``1.0`` (fully opaque). Out-of-range values
        raise :class:`ValueError`; ``NaN`` is also rejected.
        """
        if alpha != alpha:  # NaN check
            raise ValueError("alpha must be a real number in [0.0, 1.0]")
        if alpha < 0.0 or alpha > 1.0:
            raise ValueError(
                f"alpha must be in [0.0, 1.0], got {alpha!r}"
            )
        r, g, b = self.to_rgb()
        return (r, g, b, float(alpha))

    @staticmethod
    def composite_over(
        top: tuple[float, ...],
        bottom: tuple[float, ...],
        alpha: float,
    ) -> tuple[float, ...]:
        """Standard "over" alpha composite per PDF 32000-1 §11.6.5
        (Porter-Duff source-over with an opaque backdrop).

        ``top`` and ``bottom`` must have the same arity (e.g. both length
        3 for RGB or both length 4 for CMYK); component-wise blend is
        ``alpha * top[i] + (1 - alpha) * bottom[i]``. ``alpha`` is the
        source coverage in ``[0.0, 1.0]``. Components and alpha are
        clamped to ``[0.0, 1.0]`` on input and output.
        """
        if alpha != alpha:  # NaN check
            raise ValueError("alpha must be a real number in [0.0, 1.0]")
        if alpha < 0.0 or alpha > 1.0:
            raise ValueError(
                f"alpha must be in [0.0, 1.0], got {alpha!r}"
            )
        if len(top) != len(bottom):
            raise ValueError(
                "composite_over requires top and bottom of equal length, "
                f"got {len(top)} and {len(bottom)}"
            )
        a = float(alpha)
        inv = 1.0 - a
        return tuple(
            _clamp_unit(a * _clamp_unit(t) + inv * _clamp_unit(b))
            for t, b in zip(top, bottom)
        )

    def to_rgb_image(
        self, width: int = 1, height: int = 1
    ) -> object:
        """Render this color as an sRGB raster (Pillow ``Image`` instance,
        mode ``"RGB"``). Mirrors upstream
        ``PDColor.toRGBImage(WritableRaster)`` — but since pypdfbox has no
        AWT ``WritableRaster``, we accept a ``(width, height)`` pair and
        produce a uniformly-coloured Pillow image instead.
        """
        from PIL import Image

        r, g, b = self.to_rgb()
        rgb_8 = (
            int(round(_clamp_unit(r) * 255.0)),
            int(round(_clamp_unit(g) * 255.0)),
            int(round(_clamp_unit(b) * 255.0)),
        )
        return Image.new("RGB", (int(width), int(height)), rgb_8)

    def to_raw_image(
        self, width: int = 1, height: int = 1
    ) -> object:
        """Render this color in its native color space as a raster.
        Mirrors upstream ``PDColor.toRawImage(WritableRaster)``. Pillow
        only natively supports ``L`` (gray), ``RGB`` and ``CMYK`` modes,
        so for color spaces outside those three (Lab, Indexed,
        Separation, DeviceN, ICCBased, Pattern, Cal*) we fall back to
        :meth:`to_rgb_image` after converting through the standard sRGB
        path.
        """
        from PIL import Image

        name = self._color_space.get_name()
        if name == "DeviceGray":
            value = int(round(_clamp_unit(self._components[0]) * 255.0))
            return Image.new("L", (int(width), int(height)), value)
        if name == "DeviceRGB":
            rgb_8 = (
                int(round(_clamp_unit(self._components[0]) * 255.0)),
                int(round(_clamp_unit(self._components[1]) * 255.0)),
                int(round(_clamp_unit(self._components[2]) * 255.0)),
            )
            return Image.new("RGB", (int(width), int(height)), rgb_8)
        if name == "DeviceCMYK":
            cmyk_8 = (
                int(round(_clamp_unit(self._components[0]) * 255.0)),
                int(round(_clamp_unit(self._components[1]) * 255.0)),
                int(round(_clamp_unit(self._components[2]) * 255.0)),
                int(round(_clamp_unit(self._components[3]) * 255.0)),
            )
            return Image.new("CMYK", (int(width), int(height)), cmyk_8)
        return self.to_rgb_image(width, height)

    def get_java_color(self) -> tuple[float, float, float]:
        """Return the upstream ``java.awt.Color`` equivalent as a tuple of
        three floats in ``[0.0, 1.0]``. Upstream returns a
        ``java.awt.Color``; pypdfbox represents colors as tuples (see
        ``CHANGES.md`` — AWT ``Color`` → ``tuple[float, float, float]``).

        Numerically identical to :meth:`to_rgb`; kept as a separate alias
        for surface compatibility with PDFBox callers reaching for
        ``getJavaColor()``.
        """
        return self.to_rgb()

    # ---------- COS surface ----------

    def to_cos_array(self) -> COSArray:
        array = COSArray()
        for component in self._components:
            array.add(COSFloat(component))
        if self._pattern_name is not None:
            array.add(self._pattern_name)
        return array

    # ---------- value semantics ----------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PDColor):
            return NotImplemented
        return (
            self._components == other._components
            and self._color_space is other._color_space
            and self._pattern_name == other._pattern_name
        )

    def __hash__(self) -> int:
        return hash(
            (
                tuple(self._components),
                id(self._color_space),
                self._pattern_name,
            )
        )

    @classmethod
    def from_cos_array(
        cls,
        array: COSArray,
        color_space: PDColorSpace,
    ) -> PDColor:
        return cls(array, color_space)

    @staticmethod
    def _parse_cos_array(
        array: COSArray,
    ) -> tuple[list[float], COSName | None]:
        """Split a COSArray into ``(components, pattern_name)``.

        Numeric entries (``COSFloat``/``COSInteger``) become components in
        order; the trailing ``COSName`` (if present) is the pattern name.
        Mirrors upstream ``PDColor(COSArray, PDColorSpace)`` parsing.
        """
        components: list[float] = []
        pattern: COSName | None = None
        for index in range(array.size()):
            item = array.get_object(index)
            if isinstance(item, (COSFloat, COSInteger)):
                components.append(float(item.value))
            elif isinstance(item, COSName):
                pattern = item
        return components, pattern


__all__ = ["PDColor"]
