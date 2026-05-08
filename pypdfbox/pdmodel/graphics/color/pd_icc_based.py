from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.common.pd_metadata import PDMetadata
from pypdfbox.pdmodel.common.pd_stream import PDStream

from .pd_color import PDColor, _clamp_unit
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

    ICC profile bytes and COS metadata are exposed directly. sRGB
    conversion uses Pillow's ICC support when available and otherwise
    falls back to ``/Alternate`` or an alternate inferred from ``/N``.
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

    def get_default_decode(self, bits_per_component: int) -> list[float]:
        """Return the default image ``/Decode`` array for this ICCBased
        color space.

        Mirrors upstream ``PDICCBased.getDefaultDecode(int)``: each
        component's decode pair comes from that component's ``/Range``
        entry, with the PDF default ``(0.0, 1.0)`` used when ``/Range``
        is absent or too short.
        """
        out: list[float] = []
        for component in range(self.get_n()):
            low, high = self.get_range_for_component(component)
            out.append(low)
            out.append(high)
        return out

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

    def set_alternate(self, alternate: PDColorSpace | None) -> None:
        stream = self._get_stream()
        if stream is None:
            return
        if alternate is None:
            stream.remove_item(_ALTERNATE)
            return
        cos = alternate.get_cos_object()
        if cos is None:
            raise TypeError("set_alternate requires a color space with a COS form")
        stream.set_item(_ALTERNATE, cos)

    def has_alternate(self) -> bool:
        """Return ``True`` when ``/Alternate`` resolves to a color space."""
        return self.get_alternate() is not None

    def clear_alternate(self) -> None:
        """Remove ``/Alternate``. No-op if the ICC stream is malformed."""
        self.set_alternate(None)

    def get_alternate_color_space(self) -> PDColorSpace | None:
        """``/Alternate`` — typed alternate color space, or ``None``.
        Upstream-named alias of :meth:`get_alternate`. Mirrors upstream
        ``PDICCBased.getAlternateColorSpace() : PDColorSpace``."""
        return self.get_alternate()

    def set_alternate_color_space(self, alternate: PDColorSpace | None) -> None:
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

    def has_range(self) -> bool:
        """Return ``True`` when ``/Range`` is present as a ``COSArray``."""
        return self.get_range() is not None

    def clear_range(self) -> None:
        """Remove ``/Range``. Components then decode as ``(0.0, 1.0)``."""
        stream = self._get_stream()
        if stream is not None:
            stream.remove_item(_RANGE)

    def get_range_for_component(self, n: int) -> tuple[float, float]:
        """Return the ``(low, high)`` pair from ``/Range`` for component
        ``n``. Mirrors upstream
        ``PDICCBased.getRangeForComponent(int) : PDRange``. Defaults to
        ``(0.0, 1.0)`` when ``/Range`` is missing or the array is too
        short for all components — mirrors PDFBox's lenient handling of
        malformed short ``/Range`` arrays."""
        rng = self.get_range()
        if rng is None or len(rng) < self.get_n() * 2:
            return (0.0, 1.0)
        low_idx = 2 * n
        high_idx = 2 * n + 1
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

    def has_metadata(self) -> bool:
        """Return ``True`` when ``/Metadata`` is present as a stream."""
        return self.get_metadata() is not None

    def clear_metadata(self) -> None:
        """Remove ``/Metadata``. No-op if the ICC stream is malformed."""
        self.set_metadata(None)

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
        """Convert ``components`` through the embedded ICC profile when
        possible, falling back to the alternate color space otherwise.

        Per PDF 32000-1 §8.6.5.5: the ICC profile in the stream is the
        canonical converter; ``/Alternate`` (or one inferred from
        ``/N`` ∈ {1, 3, 4} → DeviceGray/DeviceRGB/DeviceCMYK) is a
        fallback for renderers that can't process the profile.

        We try Pillow's ``ImageCms`` first — when it's available *and*
        the embedded profile parses, we build an sRGB transform and run
        the ``components`` through it. On any error (malformed profile,
        unsupported component count) we silently fall through to the
        alternate-CS path so callers always get a valid sRGB tuple.
        """
        from .pd_device_cmyk import PDDeviceCMYK
        from .pd_device_gray import PDDeviceGray
        from .pd_device_rgb import PDDeviceRGB

        # Try ICC-based conversion first when Pillow is available.
        rgb = self._try_icc_to_rgb(components)
        if rgb is not None:
            return rgb

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

    def _try_icc_to_rgb(
        self, components: list[float]
    ) -> tuple[float, float, float] | None:
        """Attempt ICC-profile-driven conversion via Pillow's ``ImageCms``.

        Returns ``None`` (caller falls through to ``/Alternate``) when
        Pillow can't parse the embedded profile, the profile's component
        count doesn't match ``/N`` or our supported set (1/3/4), or any
        runtime error occurs while building / running the transform.
        """
        try:
            from io import BytesIO

            from PIL import Image, ImageCms
        except ImportError:
            return None

        profile_bytes = self.get_iccprofile_bytes()
        if not profile_bytes:
            return None

        n = self.get_n()
        if n not in (1, 3, 4):
            return None
        if len(components) < n:
            return None

        try:
            in_profile = ImageCms.ImageCmsProfile(BytesIO(profile_bytes))
        except (OSError, ValueError, ImageCms.PyCMSError):
            return None
        try:
            srgb_profile = ImageCms.createProfile("sRGB")
        except (OSError, ValueError, ImageCms.PyCMSError):
            return None

        if n == 1:
            in_mode = "L"
            sample: int | tuple[int, int, int] | tuple[int, int, int, int] = int(
                round(_clamp_unit(components[0]) * 255.0)
            )
        elif n == 3:
            in_mode = "RGB"
            sample = (
                int(round(_clamp_unit(components[0]) * 255.0)),
                int(round(_clamp_unit(components[1]) * 255.0)),
                int(round(_clamp_unit(components[2]) * 255.0)),
            )
        else:  # n == 4
            in_mode = "CMYK"
            sample = (
                int(round(_clamp_unit(components[0]) * 255.0)),
                int(round(_clamp_unit(components[1]) * 255.0)),
                int(round(_clamp_unit(components[2]) * 255.0)),
                int(round(_clamp_unit(components[3]) * 255.0)),
            )

        try:
            transform = ImageCms.buildTransform(
                in_profile, srgb_profile, in_mode, "RGB"
            )
            src = Image.new(in_mode, (1, 1), sample)
            dst = ImageCms.applyTransform(src, transform)
            if dst is None:
                return None
            pixel = dst.getpixel((0, 0))
        except (OSError, ValueError, ImageCms.PyCMSError):
            return None
        if not isinstance(pixel, tuple) or len(pixel) < 3:
            return None
        r, g, b = pixel[:3]
        return (r / 255.0, g / 255.0, b / 255.0)


__all__ = ["PDICCBased"]
