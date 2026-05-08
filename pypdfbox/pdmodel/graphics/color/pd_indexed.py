from __future__ import annotations

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
    rendering remains in the image/raster path.
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
