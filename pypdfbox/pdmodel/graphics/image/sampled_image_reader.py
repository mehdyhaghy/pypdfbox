"""Read sampled (raster) image data from a PDF.

Mirrors ``org.apache.pdfbox.pdmodel.graphics.image.SampledImageReader``.

Upstream is a 788-line utility class glued to ``javax.imageio`` and
``java.awt.image.WritableRaster``. We expose the four public static
entry points (``get_stencil_image``, ``get_rgb_image`` x2,
``get_raw_raster``) and the inner ``MultipleInputStream`` helper. The
generic bit-packed decode path now decodes arbitrary bpc (1/2/4/8/16)
with optional colour-key masking via Pillow; the raw-raster path
returns a Pillow image containing the un-colour-converted samples.
"""

from __future__ import annotations

import io
import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:

    from .pd_image import PDImage

_LOG = logging.getLogger(__name__)


class _BitReader:
    """MSB-first bit reader over a bytes-like buffer.

    Mirrors ``javax.imageio.stream.MemoryCacheImageInputStream.readBits``
    semantics for the limited shape we need: read ``n`` bits, MSB-first,
    advancing the cursor.
    """

    __slots__ = ("_data", "_byte_idx", "_bit_idx")

    def __init__(self, data: bytes) -> None:
        self._data = data
        self._byte_idx = 0
        self._bit_idx = 0  # 0..7, MSB first

    def read_bits(self, n: int) -> int:
        if n <= 0:
            return 0
        value = 0
        for _ in range(n):
            if self._byte_idx >= len(self._data):
                # Pad with zeros past EOF (matches Java's behaviour of
                # returning 0 from a short stream rather than raising).
                value <<= 1
                continue
            bit = (self._data[self._byte_idx] >> (7 - self._bit_idx)) & 1
            value = (value << 1) | bit
            self._bit_idx += 1
            if self._bit_idx == 8:
                self._bit_idx = 0
                self._byte_idx += 1
        return value

    def align_to_byte(self) -> None:
        if self._bit_idx != 0:
            self._bit_idx = 0
            self._byte_idx += 1


class SampledImageReader:
    """Static-method utility class. Constructor mirrors upstream's private one."""

    def __init__(self) -> None:  # pragma: no cover - upstream is uninstantiable
        raise TypeError("SampledImageReader is a static utility class")

    @staticmethod
    def get_stencil_image(pd_image: PDImage, paint: Any) -> Any:
        """Return an ARGB image filled with ``paint`` using ``pd_image`` as a mask.

        Mirrors upstream lines 63-136.
        """
        try:
            from PIL import Image
        except ImportError:
            return None
        width = pd_image.get_width()
        height = pd_image.get_height()
        masked = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        # Fill with the requested paint (Pillow paints solid colors directly).
        if isinstance(paint, (tuple, list)):
            fill = tuple(paint) if len(paint) == 4 else (*paint, 255)
            for y in range(height):
                for x in range(width):
                    masked.putpixel((x, y), fill)
        # Build a bit-packed mask from the stream.
        with pd_image.create_input_stream() as iis:
            data = iis.read()
        decode = _get_decode_array(pd_image)
        value = 1 if decode[0] < decode[1] else 0
        for y in range(height):
            for x in range(width):
                bit_idx = y * ((width + 7) // 8) * 8 + x
                byte_idx = bit_idx // 8
                if byte_idx >= len(data):
                    break
                bit = (data[byte_idx] >> (7 - (bit_idx % 8))) & 1
                if bit == value:
                    masked.putpixel((x, y), (0, 0, 0, 0))
        return masked

    @staticmethod
    def get_rgb_image(
        pd_image: PDImage,
        color_key_or_region: Any = None,
        subsampling: int = 1,
        color_key: Any = None,
    ) -> Any:
        """Return an ARGB-style image from the PD image.

        Upstream provides two overloads:
        - ``getRGBImage(pdImage, COSArray colorKey)`` (line 138)
        - ``getRGBImage(pdImage, Rectangle region, int subsampling, COSArray colorKey)`` (line 172)

        ``color_key_or_region`` is overloaded: if it's a 4-tuple/list it's
        treated as a region; otherwise it's treated as the colour-key
        array (matching upstream's two-argument call site).
        """
        try:
            from PIL import Image
        except ImportError:
            return None

        # Disambiguate the two-arg overload.
        region: Any = None
        if isinstance(color_key_or_region, (tuple, list)) and len(color_key_or_region) == 4 and all(
            isinstance(v, (int, float)) for v in color_key_or_region
        ):
            region = color_key_or_region
        elif color_key_or_region is not None and color_key is None:
            color_key = color_key_or_region

        if pd_image.is_empty():
            raise OSError("Image stream is empty")

        width = pd_image.get_width()
        height = pd_image.get_height()
        if width <= 0 or height <= 0:
            raise OSError("image width and height must be positive")

        clipped = SampledImageReader.clip_region(pd_image, region)
        x, y, cw, ch = clipped
        sub = max(1, int(subsampling))
        out_w = max(1, -(-cw // sub))  # ceil div
        out_h = max(1, -(-ch // sub))

        bpc = pd_image.get_bits_per_component()
        try:
            color_space = pd_image.get_color_space()
            num_components = color_space.get_number_of_components()
        except (AttributeError, OSError):
            color_space = None
            num_components = 1

        decode = _get_decode_array(pd_image)
        if len(decode) < num_components * 2:
            # Defensive — fall back to default-decode shape.
            decode = (decode + [0.0, 1.0] * num_components)[: num_components * 2]

        # Read the full stream.
        with pd_image.create_input_stream() as iis:
            data = iis.read()
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)

        sample_max = (1 << bpc) - 1 if bpc > 0 else 1

        # Parse colour-key ranges if supplied.
        color_key_ranges: list[float] | None = None
        if color_key is not None:
            try:
                if hasattr(color_key, "to_float_array"):
                    ck = list(color_key.to_float_array())
                else:
                    ck = [float(v) for v in color_key]
                if len(ck) >= num_components * 2:
                    color_key_ranges = ck
                else:
                    _LOG.warning(
                        "colorKey mask size is %d, should be %d, ignored",
                        len(ck),
                        num_components * 2,
                    )
            except (TypeError, ValueError, OSError):
                color_key_ranges = None

        # Compute per-row bit padding (matches upstream lines 622-629).
        bits_per_row = width * num_components * bpc
        padding_bits = bits_per_row % 8
        if padding_bits > 0:
            padding_bits = 8 - padding_bits

        reader = _BitReader(data)
        # Output: RGBA when colour-key mask present, else RGB.
        mode_out = "RGBA" if color_key_ranges is not None else "RGB"
        out_image = Image.new(mode_out, (out_w, out_h))
        out_pixels = out_image.load()

        for src_y in range(height):
            row_samples: list[tuple[list[int], bool]] = []
            for _src_x in range(width):
                comps: list[int] = []
                is_masked = True
                for c in range(num_components):
                    raw = reader.read_bits(bpc)
                    if color_key_ranges is not None:
                        is_masked = is_masked and (
                            raw >= color_key_ranges[c * 2]
                            and raw <= color_key_ranges[c * 2 + 1]
                        )
                    d_min = decode[c * 2]
                    d_max = decode[(c * 2) + 1]
                    if sample_max == 0:  # pragma: no cover -- bpc>=1 -> sample_max>=1
                        decoded = d_min
                    else:
                        decoded = d_min + raw * ((d_max - d_min) / sample_max)
                    span = abs(d_max - d_min) or 1.0
                    byte_val = int(round(((decoded - min(d_min, d_max)) / span) * 255.0))
                    comps.append(max(0, min(255, byte_val)))
                row_samples.append((comps, is_masked))
            reader.read_bits(padding_bits)

            # Subsample / clip the row.
            if src_y < y or src_y >= y + ch:
                continue
            if (src_y - y) % sub != 0:
                continue
            out_y = (src_y - y) // sub
            if out_y >= out_h:  # pragma: no cover -- out_h = ceil(ch/sub) bounds src_y-y
                continue
            for src_x in range(width):
                if src_x < x or src_x >= x + cw:
                    continue
                if (src_x - x) % sub != 0:
                    continue
                out_x = (src_x - x) // sub
                if out_x >= out_w:  # pragma: no cover -- out_w = ceil(cw/sub) bounds src_x-x
                    continue
                comps, is_masked = row_samples[src_x]
                # Expand grayscale -> RGB; clip CMYK / multi-channel to first 3.
                if len(comps) == 1:
                    pixel = (comps[0], comps[0], comps[0])
                elif len(comps) >= 3:
                    pixel = (comps[0], comps[1], comps[2])
                else:
                    pixel = (comps[0], comps[0], comps[0])
                if mode_out == "RGBA":
                    alpha = 0 if is_masked else 255
                    pixel = (*pixel, alpha)
                out_pixels[out_x, out_y] = pixel
        return out_image

    @staticmethod
    def get_raw_raster(pd_image: PDImage) -> Any:
        """Return the raw (un-colour-converted) raster.

        Mirrors upstream line 228. Returns a Pillow image whose mode
        matches the image's component count (``L`` for 1 channel,
        ``RGB`` for 3, ``CMYK`` for 4) holding the *decoded* sample
        values without colour-space conversion. ``None`` is returned if
        Pillow is unavailable.
        """
        try:
            from PIL import Image
        except ImportError:
            return None
        if pd_image.is_empty():
            raise OSError("Image stream is empty")
        width = pd_image.get_width()
        height = pd_image.get_height()
        if width <= 0 or height <= 0:
            raise OSError("image width and height must be positive")
        try:
            num_components = pd_image.get_color_space().get_number_of_components()
        except (AttributeError, OSError):
            num_components = 1
        bpc = pd_image.get_bits_per_component()
        decode = _get_decode_array(pd_image)
        if len(decode) < num_components * 2:
            decode = (decode + [0.0, 1.0] * num_components)[: num_components * 2]

        with pd_image.create_input_stream() as iis:
            data = iis.read()
        if not isinstance(data, (bytes, bytearray)):
            data = bytes(data)

        sample_max = (1 << bpc) - 1 if bpc > 0 else 1
        bits_per_row = width * num_components * bpc
        padding_bits = bits_per_row % 8
        if padding_bits > 0:
            padding_bits = 8 - padding_bits

        if num_components == 1:
            mode = "L"
        elif num_components == 3:
            mode = "RGB"
        elif num_components == 4:
            mode = "CMYK"
        else:
            # Pillow has no mode for >4 channels; fall back to L per-band.
            mode = "L"

        out = Image.new(mode, (width, height))
        pixels = out.load()
        reader = _BitReader(data)
        for py in range(height):
            for px in range(width):
                comps: list[int] = []
                for c in range(num_components):
                    raw = reader.read_bits(bpc)
                    d_min = decode[c * 2]
                    d_max = decode[(c * 2) + 1]
                    if sample_max == 0:  # pragma: no cover -- bpc>=1 -> sample_max>=1
                        decoded = d_min
                    else:
                        decoded = d_min + raw * ((d_max - d_min) / sample_max)
                    span = abs(d_max - d_min) or 1.0
                    byte_val = int(round(((decoded - min(d_min, d_max)) / span) * 255.0))
                    comps.append(max(0, min(255, byte_val)))
                if mode == "L":
                    pixels[px, py] = comps[0]
                elif mode == "RGB":
                    pixels[px, py] = (comps[0], comps[1], comps[2])
                elif mode == "CMYK":  # pragma: no branch  # mode exhaustively L/RGB/CMYK
                    pixels[px, py] = (comps[0], comps[1], comps[2], comps[3])
            reader.read_bits(padding_bits)
        return out

    # --- Private upstream helpers, exposed for parity --------------------

    @staticmethod
    def clip_region(pd_image: PDImage, region: Any) -> Any:
        """Mirror of ``SampledImageReader.clipRegion`` (Java line 143).

        Clamps ``region`` to the image's bounding box.
        """
        width = pd_image.get_width()
        height = pd_image.get_height()
        if region is None:
            return (0, 0, width, height)
        try:
            x, y, w, h = region
        except (TypeError, ValueError):
            return (0, 0, width, height)
        x = max(0, int(x))
        y = max(0, int(y))
        w = min(width - x, int(w))
        h = min(height - y, int(h))
        return (x, y, max(0, w), max(0, h))

    @staticmethod
    def read_raster_from_any(pd_image: PDImage, raster: Any) -> None:
        """Mirror of ``SampledImageReader.readRasterFromAny`` (Java line 265).

        Reads the raw stream bytes into the supplied raster. Our raster
        plumbing is Pillow-based; the body is a stub that defers to the
        public ``get_rgb_image`` path.
        """
        return None

    @staticmethod
    def from1_bit(
        pd_image: PDImage,
        clipped: Any,
        subsampling: int,
        target_width: int,
        target_height: int,
    ) -> Any:
        """Mirror of ``SampledImageReader.from1Bit`` (Java line 365).

        Decodes a 1-bit-per-component bilevel image. Falls back to
        ``get_rgb_image`` for the common case.
        """
        return SampledImageReader.get_rgb_image(pd_image, clipped, subsampling, None)

    @staticmethod
    def from8bit(
        pd_image: PDImage,
        raster: Any,
        clipped: Any,
        subsampling: int,
        target_width: int,
        target_height: int,
    ) -> Any:
        """Mirror of ``SampledImageReader.from8bit`` (Java line 467).

        Decodes 8-bit-per-component data.
        """
        return SampledImageReader.get_rgb_image(pd_image, clipped, subsampling, None)

    @staticmethod
    def from_any(
        pd_image: PDImage,
        raster: Any,
        color_key: Any,
        clipped: Any,
        subsampling: int,
        target_width: int,
        target_height: int,
    ) -> Any:
        """Mirror of ``SampledImageReader.fromAny`` (Java line 558)."""
        return SampledImageReader.get_rgb_image(pd_image, clipped, subsampling, color_key)

    @staticmethod
    def apply_color_key_mask(image: Any, mask: Any) -> Any:
        """Mirror of ``SampledImageReader.applyColorKeyMask`` (Java line 714).

        Applies a colour-key mask by zeroing the alpha channel where the
        mask is set. Uses Pillow's ``putalpha`` when available.
        """
        if image is None or mask is None:
            return image
        import contextlib

        try:
            from PIL import Image  # noqa: F401
        except ImportError:
            return image
        with contextlib.suppress(AttributeError, ValueError):
            image.putalpha(mask)
        return image

    @staticmethod
    def get_decode_array(pd_image: PDImage) -> list[float]:
        """Mirror of ``SampledImageReader.getDecodeArray`` (Java line 749)."""
        return _get_decode_array(pd_image)


class MultipleInputStream(io.RawIOBase):
    """Concatenates multiple ``InputStream``s into a single readable stream.

    Mirror of upstream's package-private inner class
    (``PNGConverter.MultipleInputStream`` at line 491). Surface API
    matches Java's ``InputStream``: ``read()``, ``read(buf)``, ``close()``.
    """

    def __init__(self, streams: Iterable[io.RawIOBase]) -> None:
        super().__init__()
        self._streams = list(streams)
        self._idx = 0

    def readable(self) -> bool:
        return True

    def readinto(self, b: Any) -> int:
        total = 0
        view = memoryview(b)
        while total < len(view):
            if self._idx >= len(self._streams):
                break
            n = self._streams[self._idx].readinto(view[total:])
            if not n:
                self._idx += 1
                continue
            total += n
        return total

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            chunks: list[bytes] = []
            while self._idx < len(self._streams):
                chunk = self._streams[self._idx].read()
                if not chunk:
                    self._idx += 1
                    continue
                chunks.append(chunk)
            return b"".join(chunks)
        out = bytearray()
        while len(out) < n and self._idx < len(self._streams):
            chunk = self._streams[self._idx].read(n - len(out))
            if not chunk:
                self._idx += 1
                continue
            out.extend(chunk)
        return bytes(out)

    def close(self) -> None:
        import contextlib

        for s in self._streams:
            with contextlib.suppress(OSError):
                s.close()
        super().close()


def _get_decode_array(pd_image: PDImage) -> list[float]:
    """Return the image's Decode array, defaulting to ``[0, 1]`` per component.

    ``PDImage.get_decode`` returns different shapes across the image
    hierarchy: :class:`PDImageXObject` already decodes it to a
    ``list[float]``, while :class:`PDInlineImage` returns the raw
    ``COSArray``. Normalise both so the /Decode array is honoured for
    *either* image shape (mirrors upstream ``SampledImageReader.getDecodeArray``
    which always reads ``COSArray decode = pdImage.getDecode()``)."""
    decode = pd_image.get_decode()
    # Empty COSArray and missing entry both fall back to the per-component
    # default decode (``[0 1]`` repeated). ``decode.size() == 0`` covers the
    # COSArray shape; ``len(decode) == 0`` covers the list shape.
    is_empty = (
        decode is None
        or (hasattr(decode, "size") and decode.size() == 0)
        or (isinstance(decode, list) and len(decode) == 0)
    )
    if is_empty:
        try:
            num = pd_image.get_color_space().get_number_of_components()
        except (AttributeError, OSError):
            num = 1
        return [0.0, 1.0] * num
    if isinstance(decode, list):
        return [float(v) for v in decode]
    try:
        return list(decode.to_float_array())
    except (AttributeError, TypeError):
        return [0.0, 1.0]


__all__ = ["MultipleInputStream", "SampledImageReader"]
