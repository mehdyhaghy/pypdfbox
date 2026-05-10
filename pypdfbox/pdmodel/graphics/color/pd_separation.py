from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pypdfbox.cos import COSArray, COSBase, COSName

from .pd_color import PDColor
from .pd_color_space import PDColorSpace

if TYPE_CHECKING:
    from pypdfbox.pdmodel.common.function import PDFunction


class PDSeparation(PDColorSpace):
    """A Separation color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDSeparation``.

    Array form: ``[/Separation <colorant name> <alternate CS> <tint
    transform>]``.
    """

    NAME: str = "Separation"

    # Array index constants — match upstream private fields.
    _COLORANT_NAMES = 1
    _ALTERNATE_CS = 2
    _TINT_TRANSFORM = 3

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            # Placeholders matching upstream PDSeparation() default ctor.
            array.add(COSName.get_pdf_name(""))
            array.add(COSName.get_pdf_name(""))
            array.add(COSName.get_pdf_name(""))
        super().__init__(array)
        # Initial color per upstream is a single component at 1.0 (full
        # tint).
        self._initial_color = PDColor([1.0], self)
        # Mirror upstream ``toRGBMap`` (PDSeparation.java line 64) — the
        # quantised tint -> RGB cache shared by ``toRGB`` / ``toRGBImage``.
        # ``None`` until the first call so the empty-init case stays cheap.
        self._to_rgb_map: dict[int, tuple[float, float, float]] | None = None

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Return ``[0, 1]`` per upstream — single tint component spans
        the full range. Mirrors upstream
        ``PDSeparation.getDefaultDecode``."""
        return [0.0, 1.0]

    # ---------- separation-specific ----------

    def _get_array_object(self, index: int) -> COSBase | None:
        assert self._array is not None
        if self._array.size() <= index:
            return None
        return self._array.get_object(index)

    def _ensure_array_size(self, size: int) -> None:
        assert self._array is not None
        while self._array.size() < size:
            self._array.add(COSName.get_pdf_name(""))

    def get_colorant_name(self) -> str | None:
        assert self._array is not None
        entry = self._get_array_object(self._COLORANT_NAMES)
        if isinstance(entry, COSName):
            return entry.get_name()
        return None

    def set_colorant_name(self, name: str) -> None:
        assert self._array is not None
        self._ensure_array_size(self._COLORANT_NAMES + 1)
        self._array.set(self._COLORANT_NAMES, COSName.get_pdf_name(name))

    def get_alternate_color_space(self) -> PDColorSpace | None:
        assert self._array is not None
        entry = self._get_array_object(self._ALTERNATE_CS)
        if entry is None:
            return None
        return PDColorSpace.create(entry)

    def set_alternate_color_space(self, alternate: PDColorSpace) -> None:
        assert self._array is not None
        self._ensure_array_size(self._ALTERNATE_CS + 1)
        cos = alternate.get_cos_object()
        if cos is None:
            raise TypeError(
                "set_alternate_color_space requires a color space with a COS form"
            )
        self._array.set(self._ALTERNATE_CS, cos)

    def has_alternate_color_space(self) -> bool:
        """Return ``True`` when the alternate-CS slot resolves."""
        return self.get_alternate_color_space() is not None

    def get_tint_transform(self) -> PDFunction | None:
        """Return the tint transform as a :class:`PDFunction`. Mirrors
        upstream ``PDSeparation.getTintTransform()``.

        Returns ``None`` for placeholder slots that don't dispatch to a
        concrete function type — keep the default ctor's empty-name
        slot from blowing up callers that probe before populating.
        """
        from pypdfbox.pdmodel.common.function import PDFunction

        raw = self.get_tint_transform_cos()
        if raw is None:
            return None
        try:
            return PDFunction.create(raw)
        except (TypeError, ValueError):
            return None

    def get_tint_transform_cos(self) -> COSBase | None:
        """Return the raw tint transform COS object (function dictionary
        or stream). Pypdfbox enrichment — upstream exposes only the
        typed ``PDFunction`` accessor."""
        assert self._array is not None
        return self._get_array_object(self._TINT_TRANSFORM)

    def has_tint_transform(self) -> bool:
        """Return ``True`` when the tint-transform slot resolves to a function."""
        return self.get_tint_transform() is not None

    def clear_tint_transform(self) -> None:
        """Clear the tint-transform slot back to the default placeholder."""
        assert self._array is not None
        self._ensure_array_size(self._TINT_TRANSFORM + 1)
        self._array.set(self._TINT_TRANSFORM, COSName.get_pdf_name(""))

    def set_tint_transform(self, transform: object) -> None:
        """Store the tint transform. Accepts either a :class:`PDFunction`
        (upstream signature) or a raw COS object (pypdfbox enrichment).
        """
        assert self._array is not None
        self._ensure_array_size(self._TINT_TRANSFORM + 1)
        if hasattr(transform, "get_cos_object"):
            cos = transform.get_cos_object()
            if cos is None:
                raise TypeError(
                    "set_tint_transform requires an object with a COS form"
                )
            self._array.set(self._TINT_TRANSFORM, cos)
        elif isinstance(transform, COSBase):
            self._array.set(self._TINT_TRANSFORM, transform)
        else:
            raise TypeError(
                "set_tint_transform expects PDFunction or COSBase, "
                f"got {type(transform).__name__}"
            )

    # ---------- string form ----------

    def __str__(self) -> str:
        """Mirrors upstream ``PDSeparation.toString``:
        ``Separation{"<colorant>" <alternate name> <tint>}``.

        ``<colorant>`` is the empty string for a default-ctor placeholder
        slot; ``<alternate name>`` falls back to ``None`` when the
        alternate slot can't be resolved (matches the lenient lite-path
        behaviour of :meth:`get_alternate_color_space`).
        """
        colorant = self.get_colorant_name() or ""
        alternate = self.get_alternate_color_space()
        alt_name = alternate.get_name() if alternate is not None else "None"
        tint = self.get_tint_transform()
        tint_repr = "None" if tint is None else str(tint)
        return f'{self.get_name()}{{"{colorant}" {alt_name} {tint_repr}}}'

    # ---------- conversion ----------

    def to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Evaluate the tint transform and forward to the alternate CS.

        Per PDF 32000-1 §8.6.6.4, ``components`` is the single tint
        value in ``[0, 1]``. The tint transform (a PDF function) maps
        it to coordinates in the alternate color space, which then
        produces the RGB output. Mirrors upstream
        ``PDSeparation.toRGB(float[])`` (PDSeparation.java line 137),
        including the ``toRGBMap`` quantised cache keyed on
        ``(int)(tint * 255)``.
        """
        alternate = self.get_alternate_color_space()
        if alternate is None:
            return None
        function = self.get_tint_transform()
        if function is None:
            return None
        if self._to_rgb_map is None:
            self._to_rgb_map = {}
        key = int(components[0] * 255)
        cached = self._to_rgb_map.get(key)
        if cached is not None:
            return cached
        alt_components = function.eval(list(components))
        result = PDColor(alt_components, alternate).to_rgb()
        if result is None:
            return None
        self._to_rgb_map[key] = result
        return result

    # ---------- raster conversion ----------

    def tint_transform(
        self, samples: list[float], alt: list[int]
    ) -> list[int]:
        """Map a single 8-bit tint sample through the tint-transform
        function into integer alternate-CS components in ``[0, 255]``.
        Mirrors upstream protected helper
        ``PDSeparation.tintTransform(float[] samples, int[] alt)``
        (PDSeparation.java line 246)::

            samples[0] /= 255;            // 0..1
            float[] result = tintTransform.eval(samples);
            for (int s = 0; s < alt.length; s++)
                alt[s] = (int)(result[s] * 255);

        The Python signature returns the populated ``alt`` list for
        idiomatic use; ``samples`` and ``alt`` are mutated in place to
        preserve upstream's by-reference contract.
        """
        function = self.get_tint_transform()
        if function is None:
            raise ValueError(
                "PDSeparation.tint_transform requires a tint-transform function"
            )
        samples[0] = samples[0] / 255.0  # scale 0..255 -> 0..1
        result = function.eval(list(samples))
        for s in range(len(alt)):
            alt[s] = int(result[s] * 255)
        return alt

    def to_rgb_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Render an 8-bit-per-component Separation raster to a Pillow
        sRGB image. Mirrors upstream
        ``PDSeparation.toRGBImage(WritableRaster)`` (PDSeparation.java
        line 159):

        - When the alternate is :class:`PDLab` (PDFBOX-3622) or an
          ICCBased that ultimately wraps a Lab profile (PDFBOX-5778),
          short-circuit to :meth:`to_rgb_image2`.
        - Otherwise iterate every pixel, fan out the tint into the
          alternate CS via :meth:`tint_transform`, and forward the
          resulting alternate-CS raster to ``alternateColorSpace.to_rgb_image``.

        The per-tint cache (``calculatedValues`` upstream) avoids
        re-evaluating the tint transform for repeated samples.
        """
        from .pd_icc_based import PDICCBased
        from .pd_lab import PDLab

        alternate = self.get_alternate_color_space()
        if alternate is None:
            return super().to_rgb_image(raster, width, height)

        if isinstance(alternate, PDLab):
            return self.to_rgb_image2(raster, width, height)
        if isinstance(alternate, PDICCBased):
            inner = alternate.get_alternate_color_space()
            if isinstance(inner, PDLab):
                return self.to_rgb_image2(raster, width, height)

        num_alt = alternate.get_number_of_components()
        w = int(width)
        h = int(height)
        expected = w * h
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))

        # Pre-compute the tint-transform output for each unique sample
        # value (mirrors upstream ``calculatedValues`` map keyed on the
        # bit pattern of the float sample).
        cache: dict[int, list[int]] = {}
        out = bytearray(w * h * num_alt)
        for pixel_index in range(w * h):
            sample = data[pixel_index]
            alt_components = cache.get(sample)
            if alt_components is None:
                alt_components = [0] * num_alt
                self.tint_transform([float(sample)], alt_components)
                cache[sample] = alt_components
            base = pixel_index * num_alt
            for c in range(num_alt):
                out[base + c] = max(0, min(255, alt_components[c]))

        return alternate.to_rgb_image(bytes(out), w, h)

    def to_rgb_image2(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Lab-friendly converter that bypasses the alternate's raster
        path. Mirrors private upstream helper
        ``PDSeparation.toRGBImage2(WritableRaster)`` (PDSeparation.java
        line 212): for each tint sample, scale to ``[0, 1]``, evaluate
        the tint transform, route through ``alternateColorSpace.toRGB``,
        and pack the resulting RGB triple.

        Surfaced as public-named for snake_case mirror compatibility —
        upstream marks it ``private`` but parity scanners track it as
        a method on the class surface.
        """
        from PIL import Image

        alternate = self.get_alternate_color_space()
        if alternate is None:
            return super().to_rgb_image(raster, width, height)
        function = self.get_tint_transform()
        if function is None:
            return super().to_rgb_image(raster, width, height)

        w = int(width)
        h = int(height)
        expected = w * h
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))

        cache: dict[int, tuple[int, int, int]] = {}
        out = bytearray(w * h * 3)
        for pixel_index in range(w * h):
            sample = data[pixel_index]
            rgb = cache.get(sample)
            if rgb is None:
                scaled = sample / 255.0
                alt_components = function.eval([scaled])
                fltab = alternate.to_rgb(alt_components)
                if fltab is None:
                    rgb = (0, 0, 0)
                else:
                    rgb = (
                        int(fltab[0] * 255),
                        int(fltab[1] * 255),
                        int(fltab[2] * 255),
                    )
                cache[sample] = rgb
            base = pixel_index * 3
            out[base] = max(0, min(255, rgb[0]))
            out[base + 1] = max(0, min(255, rgb[1]))
            out[base + 2] = max(0, min(255, rgb[2]))
        return Image.frombytes("RGB", (w, h), bytes(out))

    def to_raw_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Wrap a Separation raster as a single-band Pillow ``L`` image.
        Mirrors upstream ``PDSeparation.toRawImage(WritableRaster)``
        (PDSeparation.java line 258), which calls the protected overload
        with ``ColorSpace.getInstance(ColorSpace.CS_GRAY)`` — the tint
        ramp is treated as 8-bit grayscale.
        """
        from PIL import Image

        w = int(width)
        h = int(height)
        expected = w * h
        data = bytes(raster)
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))
        return Image.frombytes("L", (w, h), data[:expected])

    # ---------- string form ----------

    def to_string(self) -> str:
        """Return the upstream-style ``toString`` rendering. Mirrors
        upstream ``PDSeparation.toString()`` (PDSeparation.java line
        317). Surfaced explicitly so callers porting from PDFBox can
        keep the literal ``.toString()`` invocation spelled snake_case.
        """
        return self.__str__()


__all__ = ["PDSeparation"]
