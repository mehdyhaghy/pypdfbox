from __future__ import annotations

from typing import Any

from pypdfbox.cos import (
    COSArray,
    COSBase,
    COSInteger,
    COSName,
    COSNull,
    COSStream,
    COSString,
)

from .pd_color import PDColor
from .pd_color_space import PDColorSpace
from .pd_device_rgb import PDDeviceRGB


class PDIndexed(PDColorSpace):
    """An Indexed color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDIndexed``.

    Array form: ``[/Indexed <base CS> <hival> <lookup>]``.

    The lookup table is exposed as decoded bytes and is used by
    :class:`PDColor` for best-effort sRGB conversion. Full indexed-image
    rendering goes through :meth:`to_rgb_image` (per-pixel palette
    decode) and :meth:`to_raw_image` (a Pillow ``P``-mode shortcut for
    sRGB-compatible bases).
    """

    NAME: str = "Indexed"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            array.add(PDDeviceRGB.INSTANCE.get_cos_object())
            array.add(COSInteger.get(255))
            array.add(COSNull.NULL)
        super().__init__(array)
        self._initial_color = PDColor([0.0], self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return 1

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- indexed-specific ----------

    def _get_array_object(self, index: int) -> COSBase | None:
        assert self._array is not None
        if self._array.size() <= index:
            return None
        return self._array.get_object(index)

    def _ensure_array_size(self, size: int) -> None:
        assert self._array is not None
        while self._array.size() < size:
            self._array.add(COSNull.NULL)

    def get_base_color_space(self) -> PDColorSpace | None:
        assert self._array is not None
        base = self._get_array_object(1)
        if base is None:
            return None
        return PDColorSpace.create(base)

    def set_base_color_space(self, base: PDColorSpace) -> None:
        assert self._array is not None
        self._ensure_array_size(2)
        cos = base.get_cos_object()
        if cos is None:
            raise TypeError(
                "set_base_color_space requires a color space with a COS form"
            )
        self._array.set(1, cos)

    def has_base_color_space(self) -> bool:
        """Return ``True`` when the base color-space slot resolves."""
        return self.get_base_color_space() is not None

    def get_hival(self) -> int:
        assert self._array is not None
        if self._array.size() <= 2:
            return 0
        return max(0, min(self._array.get_int(2, 0), 255))

    def set_hival(self, hival: int) -> None:
        assert self._array is not None
        self._ensure_array_size(3)
        self._array.set(2, COSInteger.get(hival))

    def get_lookup_data(self) -> bytes | None:
        """Return the lookup-table bytes for this Indexed color space.

        Per PDF 32000-1 §8.6.6.3 ``/Lookup`` is either a ``COSString``
        (literal palette bytes) or a ``COSStream`` (same logical bytes,
        carried through the stream's ``/Filter`` chain — typically
        ``/FlateDecode`` for large palettes). For the stream form we
        consume :meth:`COSStream.create_input_stream`, which walks the
        filter chain, so the caller always sees decoded palette bytes.

        Output length is clamped to ``(hival + 1) * base_components``:
        longer payloads are truncated, shorter payloads are right-padded
        with ``\x00``. Mirrors upstream's lenient handling of malformed
        indexed lookups (better a black palette entry than a crash).
        """
        assert self._array is not None
        entry = self._get_array_object(3)
        data: bytes | None = None
        if isinstance(entry, COSString):
            data = entry.get_bytes()
        elif isinstance(entry, COSStream):
            with entry.create_input_stream() as src:
                data = src.read()
        if data is None:
            return None

        base = self.get_base_color_space()
        if base is None:
            return data
        expected = (self.get_hival() + 1) * base.get_number_of_components()
        if len(data) > expected:
            return data[:expected]
        if len(data) < expected:
            return data + b"\x00" * (expected - len(data))
        return data

    def set_lookup_data(self, data: bytes | None) -> None:
        assert self._array is not None
        self._ensure_array_size(4)
        if data is None:
            self._array.set(3, COSNull.NULL)
        else:
            self._array.set(3, COSString(data))

    def has_lookup_data(self) -> bool:
        """Return ``True`` when ``/Lookup`` is present as a string or stream."""
        assert self._array is not None
        entry = self._get_array_object(3)
        return isinstance(entry, (COSString, COSStream))

    def clear_lookup_data(self) -> None:
        """Clear ``/Lookup`` by writing the Indexed null placeholder."""
        self.set_lookup_data(None)

    # ---------- private helpers (port of upstream private methods) ----------
    #
    # Upstream caches `lookupData`, `colorTable`, `actualMaxIndex`, and
    # `rgbColorTable` in fields populated by `readLookupData()`,
    # `readColorTable()`, and `initRgbColorTable()`. We mirror those
    # helpers so the behavior — read /Lookup, build the [n][k] palette,
    # convert each entry through the base CS to RGB once — has the same
    # shape on the Python side. They stay private (leading underscore)
    # to match upstream's `private` access.

    def _read_lookup_data(self) -> bytes:
        """Port of upstream ``readLookupData``: pull the /Lookup bytes
        out of either ``COSString`` or ``COSStream``; ``b""`` for any
        unsupported slot type (upstream raises ``IOException`` here, but
        pypdfbox stays lenient as documented in :meth:`get_lookup_data`).
        """
        assert self._array is not None
        entry = self._get_array_object(3)
        if isinstance(entry, COSString):
            return entry.get_bytes()
        if isinstance(entry, COSStream):
            with entry.create_input_stream() as src:
                return src.read()
        return b""

    def _read_color_table(self) -> tuple[list[list[float]], int]:
        """Port of upstream ``readColorTable``: return the ``[n][k]``
        palette as floats in ``[0, 1]`` and the actual max index after
        clamping ``hival`` against the available lookup data length.
        """
        lookup = self._read_lookup_data()
        max_index = min(self.get_hival(), 255)
        base = self.get_base_color_space()
        n = base.get_number_of_components() if base is not None else 3
        if n <= 0:
            n = 1
        # Upstream: when the lookup is too short, shrink max_index so the
        # decode loop stays in-bounds. We mirror that (no padding here —
        # padding belongs to `get_lookup_data` for the caller-facing API).
        if len(lookup) // n < max_index + 1:
            max_index = len(lookup) // n - 1
        if max_index < 0:
            return [], -1
        table: list[list[float]] = [[0.0] * n for _ in range(max_index + 1)]
        offset = 0
        for i in range(max_index + 1):
            for c in range(n):
                table[i][c] = (lookup[offset] & 0xFF) / 255.0
                offset += 1
        return table, max_index

    def _init_rgb_color_table(self) -> list[tuple[int, int, int]]:
        """Port of upstream ``initRgbColorTable``: convert each palette
        entry through the base color space to an ``(r, g, b)`` triple of
        ``int`` in ``[0, 255]``.

        Upstream builds a 1-row ``BufferedImage`` and lets the base
        color space's ``toRGBImage`` do the conversion. We achieve the
        same outcome by routing each entry through
        :meth:`PDColor.to_rgb`, which dispatches on the base color
        space's name (DeviceRGB / DeviceGray / DeviceCMYK / Cal* / Lab /
        ICCBased / Separation / DeviceN). Result is stable per call —
        callers that need caching should hold onto the list.
        """
        table, max_index = self._read_color_table()
        if max_index < 0:
            return []
        base = self.get_base_color_space()
        rgb_table: list[tuple[int, int, int]] = []
        for entry in table:
            if base is None:
                # No base CS → fall back to 3-byte DeviceRGB-style read.
                vals = (entry + [0.0, 0.0, 0.0])[:3]
                rgb_table.append(
                    (
                        max(0, min(255, int(round(vals[0] * 255.0)))),
                        max(0, min(255, int(round(vals[1] * 255.0)))),
                        max(0, min(255, int(round(vals[2] * 255.0)))),
                    )
                )
                continue
            r, g, b = PDColor(list(entry), base).to_rgb()
            rgb_table.append(
                (
                    max(0, min(255, int(round(r * 255.0)))),
                    max(0, min(255, int(round(g * 255.0)))),
                    max(0, min(255, int(round(b * 255.0)))),
                )
            )
        return rgb_table

    # ---------- conversion ----------

    def to_rgb(self, value: list[float]) -> list[float]:
        """Convert a single-component Indexed sample to sRGB floats in
        ``[0.0, 1.0]``. Mirrors upstream
        ``PDIndexed.toRGB(float[])`` (line 173): one component, clamp
        index to ``[0, actual_max_index]``, dereference the cached RGB
        table, divide by 255.

        Raises :class:`ValueError` when ``value`` is not a one-element
        sequence (upstream throws ``IllegalArgumentException``).
        """
        if len(value) != 1:
            raise ValueError(
                "Indexed color spaces must have one color value"
            )
        rgb_table = self._init_rgb_color_table()
        if not rgb_table:
            return [0.0, 0.0, 0.0]
        index = int(round(value[0]))
        if index < 0:
            index = 0
        max_index = len(rgb_table) - 1
        if index > max_index:
            index = max_index
        r, g, b = rgb_table[index]
        return [r / 255.0, g / 255.0, b / 255.0]

    def to_rgb_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Decode an indexed raster into an sRGB Pillow ``Image``.
        Mirrors upstream ``PDIndexed.toRGBImage(WritableRaster)`` (line
        194): one byte per pixel is treated as an index into the cached
        RGB lookup table, clamped to ``actual_max_index``.

        Library-first: we hand the palette to Pillow via a ``"P"``-mode
        image and ``Image.convert("RGB")`` so the lookup happens in C
        rather than per-pixel Python.
        """
        from PIL import Image

        w = int(width)
        h = int(height)
        rgb_table = self._init_rgb_color_table()
        if not rgb_table:
            return Image.new("RGB", (w, h), (0, 0, 0))
        max_index = len(rgb_table) - 1
        # Build a 768-byte Pillow palette (R0,G0,B0,R1,G1,B1,...,padded
        # with zero entries) and clamp incoming indices to max_index so
        # we never reach a zeroed slot for an out-of-range index.
        palette = bytearray(768)
        for i, (r, g, b) in enumerate(rgb_table):
            palette[i * 3] = r
            palette[i * 3 + 1] = g
            palette[i * 3 + 2] = b
        data = bytes(raster)
        expected = w * h
        if len(data) < expected:
            data = data + b"\x00" * (expected - len(data))
        elif len(data) > expected:
            data = data[:expected]
        if max_index < 255:
            # Clamp every pixel to a valid palette slot in C via bytes
            # translation rather than a Python per-pixel loop.
            translation = bytes(
                min(i, max_index) for i in range(256)
            )
            data = data.translate(translation)
        img = Image.frombytes("P", (w, h), data)
        img.putpalette(bytes(palette))
        return img.convert("RGB")

    def to_raw_image(
        self, raster: bytes, width: int, height: int
    ) -> Any:
        """Return the indexed raster as a Pillow image. Mirrors upstream
        ``PDIndexed.toRawImage(WritableRaster)`` (line 219): upstream
        returns a ``BufferedImage`` backed by an ``IndexColorModel``
        only when the base is an sRGB :class:`PDICCBased`; for any
        other base it returns ``None``.

        Lite divergence: pypdfbox returns the palette-decoded RGB image
        for every base color space, since callers in this port use
        ``to_raw_image`` as "give me the most-faithful Pillow image you
        can" rather than upstream's render-time fast path. The
        functional output (the visible pixels) is identical to
        upstream's ``IndexColorModel``-backed ``BufferedImage`` once
        rasterised, so renderers see the same image either way.
        """
        return self.to_rgb_image(raster, width, height)

    # ---------- decode ----------

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Default ``/Decode`` for Indexed images is
        ``[0, 2**bits_per_component - 1]`` per PDF 32000-1 §8.9.5.1
        Table 90 — the index range, not the [0, 1] of regular CSes.
        """
        upper = float((1 << int(bits_per_component)) - 1)
        return [0.0, upper]

    # ---------- string form ----------

    def __str__(self) -> str:
        """Mirrors upstream ``PDIndexed.toString``:
        ``Indexed{base:<base> hival:<n> lookup:(<n> entries)}``.

        ``lookup`` reports the count of palette entries (``hival + 1``,
        clamped by the actual lookup-table length when malformed). Falls
        back to ``0 entries`` when the lookup data is missing entirely
        (still useful for diagnostics).
        """
        base = self.get_base_color_space()
        base_repr = base.get_name() if base is not None else "None"
        hival = self.get_hival()
        data = self.get_lookup_data()
        if data is None or base is None:
            entries = 0
        else:
            n = base.get_number_of_components()
            entries = (len(data) // n) if n > 0 else 0
        return f"Indexed{{base:{base_repr} hival:{hival} lookup:({entries} entries)}}"


__all__ = ["PDIndexed"]
