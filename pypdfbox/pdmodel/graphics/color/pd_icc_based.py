from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.common.pd_stream import PDStream

from .pd_color import PDColor
from .pd_color_space import PDColorSpace


_N: COSName = COSName.get_pdf_name("N")
_ALTERNATE: COSName = COSName.get_pdf_name("Alternate")
_RANGE: COSName = COSName.get_pdf_name("Range")
_METADATA: COSName = COSName.get_pdf_name("Metadata")


class PDICCBased(PDColorSpace):
    """An ICCBased color space. Mirrors PDFBox
    ``org.apache.pdfbox.pdmodel.graphics.color.PDICCBased``.

    Array form: ``[/ICCBased <stream>]`` where the stream's dictionary
    carries ``/N`` (component count), ``/Alternate``, ``/Range``,
    ``/Metadata`` and the stream body holds the raw ICC profile bytes.

    Lite surface: ICC profile parsing, validation and color conversion
    are deferred (CLAUDE.md library-first note — when implemented they
    will wrap a permissive ICC library, never reimplement). For now we
    expose just the COS surface.
    """

    NAME: str = "ICCBased"

    def __init__(self, array: COSArray | None = None) -> None:
        if array is None:
            array = COSArray()
            array.add(COSName.get_pdf_name(self.NAME))
            stream = COSStream()
            stream.set_int(_N, 3)
            array.add(stream)
        super().__init__(array)
        n = self.get_n()
        self._initial_color = PDColor([0.0] * n, self)

    # ---------- abstract surface ----------

    def get_name(self) -> str:
        return self.NAME

    def get_number_of_components(self) -> int:
        return self.get_n()

    def get_initial_color(self) -> PDColor:
        return self._initial_color

    # ---------- ICCBased-specific ----------

    def _get_stream(self) -> COSStream | None:
        assert self._array is not None
        entry = self._array.get_object(1)
        if isinstance(entry, COSStream):
            return entry
        return None

    def get_pdstream(self) -> COSStream | None:
        """Return the underlying COSStream carrying the ICC profile."""
        return self._get_stream()

    def get_pd_stream(self) -> PDStream | None:
        """Return the underlying ICC profile stream wrapped as a
        :class:`PDStream`. Mirrors upstream
        ``PDICCBased.getPDStream() : PDStream``. Returns ``None`` when
        the array's second entry is not a stream."""
        stream = self._get_stream()
        if stream is None:
            return None
        return PDStream(stream)

    def get_n(self) -> int:
        """``/N`` — number of color components (1, 3, or 4). Mirrors
        upstream ``PDICCBased.getNumberOfComponents()`` /
        ``getN() : int``. Default is ``0`` (invalid) when the stream is
        absent or ``/N`` is missing — matches upstream's
        ``getInt(COSName.N, 0)``."""
        stream = self._get_stream()
        if stream is None:
            return 0
        return stream.get_int(_N, 0)

    def set_n(self, n: int) -> None:
        """Set ``/N`` (number of color components)."""
        stream = self._get_stream()
        if stream is None:
            return
        stream.set_int(_N, int(n))

    def get_alternate(self) -> PDColorSpace | None:
        stream = self._get_stream()
        if stream is None:
            return None
        alt = stream.get_dictionary_object(_ALTERNATE)
        if alt is None:
            return None
        return PDColorSpace.create(alt)

    def set_alternate(self, alternate: PDColorSpace) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        stream.set_item(_ALTERNATE, alternate.get_cos_object())

    def get_alternate_color_space(self) -> PDColorSpace | None:
        """``/Alternate`` — typed alternate color space, or ``None``.
        Upstream-named alias of :meth:`get_alternate`. Mirrors upstream
        ``PDICCBased.getAlternateColorSpace() : PDColorSpace``."""
        return self.get_alternate()

    def set_alternate_color_space(self, alternate: PDColorSpace) -> None:
        """Upstream-named alias of :meth:`set_alternate`."""
        self.set_alternate(alternate)

    def get_range(self) -> COSArray | None:
        stream = self._get_stream()
        if stream is None:
            return None
        entry = stream.get_dictionary_object(_RANGE)
        if isinstance(entry, COSArray):
            return entry
        return None

    def set_range(self, range_array: COSArray) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        stream.set_item(_RANGE, range_array)

    def get_range_for_component(self, n: int) -> tuple[float, float]:
        """Return the ``(low, high)`` pair from ``/Range`` for component
        ``n``. Mirrors upstream
        ``PDICCBased.getRangeForComponent(int) : PDRange``. Defaults to
        ``(0.0, 1.0)`` when ``/Range`` is missing or the slot for ``n``
        is absent — matches PDF 32000-1 §8.6.5.5."""
        rng = self.get_range()
        if rng is None:
            return (0.0, 1.0)
        low_idx = 2 * n
        high_idx = 2 * n + 1
        if high_idx >= len(rng):
            return (0.0, 1.0)
        floats = rng.to_float_array()
        return (float(floats[low_idx]), float(floats[high_idx]))

    def set_range_for_component(self, n: int, low: float, high: float) -> None:
        """Set the ``(low, high)`` pair on ``/Range`` for component ``n``.
        Grows ``/Range`` (padding intermediate slots with the default
        ``(0.0, 1.0)``) when ``n`` is past the current end. Mirrors
        upstream ``PDICCBased.setRangeForComponent(PDRange, int)`` shape
        with positional ``low``/``high`` instead of a ``PDRange`` value
        type (we don't have a ``PDRange`` class in the lite surface)."""
        stream = self._get_stream()
        if stream is None:
            return
        rng = self.get_range()
        if rng is None:
            rng = COSArray()
            stream.set_item(_RANGE, rng)
        # Pad intermediate slots with the default (0.0, 1.0) pair so the
        # requested component index lands at a valid offset.
        required = 2 * (n + 1)
        while len(rng) < required - 2:
            rng.add(COSFloat(0.0))
            rng.add(COSFloat(1.0))
        if len(rng) < required:
            # Append the requested pair directly.
            rng.add(COSFloat(float(low)))
            rng.add(COSFloat(float(high)))
        else:
            rng.set(2 * n, COSFloat(float(low)))
            rng.set(2 * n + 1, COSFloat(float(high)))

    def get_metadata(self) -> PDMetadata | None:
        """``/Metadata`` — XMP metadata stream wrapped as
        :class:`PDMetadata`, or ``None``. Mirrors upstream
        ``PDICCBased.getMetadata() : PDMetadata``."""
        stream = self._get_stream()
        if stream is None:
            return None
        entry = stream.get_dictionary_object(_METADATA)
        if isinstance(entry, COSStream):
            return PDMetadata(entry)
        return None

    def set_metadata(self, metadata: PDMetadata | COSStream | None) -> None:
        """Set ``/Metadata`` (or remove when ``None``). Accepts a
        :class:`PDMetadata` (unwrapped to its underlying ``COSStream``)
        or a raw ``COSStream``."""
        stream = self._get_stream()
        if stream is None:
            return
        if metadata is None:
            stream.remove_item(_METADATA)
            return
        if isinstance(metadata, PDMetadata):
            stream.set_item(_METADATA, metadata.get_cos_object())
            return
        stream.set_item(_METADATA, metadata)

    def get_iccprofile_bytes(self) -> bytes:
        """Return the decoded ICC profile body as raw bytes. Mirrors
        upstream ``PDICCBased`` accessing the underlying stream via
        ``getPDStream().createInputStream()``. Empty/absent stream →
        ``b""``."""
        pd_stream = self.get_pd_stream()
        if pd_stream is None:
            return b""
        with pd_stream.create_input_stream() as src:
            return src.read()

    # ---------- conversion ----------

    def to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Convert ``components`` through the alternate color space.

        Lite surface: no embedded ICC profile is parsed. Per PDF 32000-1
        §8.6.5.5, the ``/Alternate`` entry provides a fallback color
        space; if absent we infer one from ``/N``: ``1`` → DeviceGray,
        ``3`` → DeviceRGB, ``4`` → DeviceCMYK. ICC profile parsing is
        deferred (CLAUDE.md library-first note — when implemented it
        will wrap a permissive ICC library, never reimplement).
        """
        from .pd_device_cmyk import PDDeviceCMYK
        from .pd_device_gray import PDDeviceGray
        from .pd_device_rgb import PDDeviceRGB

        alternate = self.get_alternate()
        if alternate is None:
            n = self.get_n()
            if n == 1:
                alternate = PDDeviceGray.INSTANCE
            elif n == 3:
                alternate = PDDeviceRGB.INSTANCE
            elif n == 4:
                alternate = PDDeviceCMYK.INSTANCE
            else:
                return None
        # Build a PDColor in the alternate CS and let it dispatch.
        return PDColor(components, alternate).to_rgb()


__all__ = ["PDICCBased"]
