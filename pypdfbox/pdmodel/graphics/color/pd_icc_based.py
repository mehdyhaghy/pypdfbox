from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSStream

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

    def get_n(self) -> int:
        stream = self._get_stream()
        if stream is None:
            return 3
        return stream.get_int(_N, 3)

    def set_n(self, n: int) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        stream.set_int(_N, n)

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

    def get_metadata(self) -> COSStream | None:
        stream = self._get_stream()
        if stream is None:
            return None
        entry = stream.get_dictionary_object(_METADATA)
        if isinstance(entry, COSStream):
            return entry
        return None

    def set_metadata(self, metadata: COSStream) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        stream.set_item(_METADATA, metadata)

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
