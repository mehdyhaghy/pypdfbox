from __future__ import annotations

import io
from typing import BinaryIO

import imagecodecs
from PIL import Image

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory


def _mode_components_and_bpc(mode: str, bands: tuple[str, ...]) -> tuple[int, int]:
    # Pillow may include byte-order suffixes for 16-bit grayscale images.
    if mode.startswith("I;16"):
        return 1, 16
    if mode == "L":
        return 1, 8
    if mode == "RGB":
        return 3, 8
    if mode in {"RGBA", "CMYK"}:
        return 4, 8
    if mode == "1":
        return 1, 1
    return len(bands), 8


def _encode_mode_for(num_components: int, bpc: int) -> str:
    """Choose the Pillow image mode for a raw raster with the given
    component count and bits-per-component.

    PDF /JPXDecode source images are always one of the four
    grayscale/RGB/CMYK shapes a PDF image XObject can express. We map:

      - 1 component, 16 bpc → "I;16" (high-precision grayscale)
      - 1 component, 8 bpc  → "L"   (grayscale)
      - 3 components        → "RGB"
      - 4 components        → "CMYK"

    Other shapes are not representable as a PDF image and raise so
    callers see the failure at encode-time rather than producing a
    spec-illegal stream.
    """
    if num_components == 1:
        if bpc == 16:
            return "I;16"
        return "L"
    if num_components == 3:
        return "RGB"
    if num_components == 4:
        return "CMYK"
    raise ValueError(
        f"JPXDecode.encode: unsupported raster shape "
        f"(components={num_components}, bpc={bpc})"
    )


class JPXDecode(Filter):
    """``/JPXDecode`` filter (ISO 32000-1 §7.4.9).

    Decodes a JPEG 2000 (JP2 / JPX / raw J2K) codestream by delegating to
    :func:`imagecodecs.jpeg2k_decode` (OpenJPEG-backed, same backend
    Pillow's plugin uses but exposed via a thin C API). Falls back to
    Pillow's ``Jpeg2KImagePlugin`` for the 16-bit grayscale path and as
    a general safety net so byte-order semantics for 16-bpc samples
    remain Pillow's well-tested ``I;16B`` (big-endian, PDF-canonical).
    Encoding stays on Pillow's OpenJPEG bridge because imagecodecs'
    encoder requires extra configuration to reproduce Pillow's default
    JP2-container output.

    Upstream ``JPXFilter`` raises on encode because Java's standard
    library has no JPEG 2000 encoder — the missing capability is
    Java-stack-specific, not a PDFBox design choice. Pillow's OpenJPEG
    bridge does support encoding, so we wire the encode path through it
    while keeping the decode behaviour byte-for-byte compatible with
    upstream.

    Per the spec the decoder must surface the codestream's intrinsic
    geometry (``/Width``, ``/Height``, ``/BitsPerComponent``, and number
    of components) when those entries are missing on the parent image
    XObject. We populate ``DecodeResult.parameters`` with the resolved
    values so callers can patch the image dictionary.

    Mirrors `org.apache.pdfbox.filter.JPXFilter`.
    """

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        encoded_bytes = encoded.read()
        out_params = COSDictionary()
        if parameters is not None:
            out_params.add_all(parameters)
        if not encoded_bytes:
            return DecodeResult(parameters=out_params, bytes_written=0)

        samples: bytes
        width: int
        height: int
        num_components: int
        bpc: int

        # Primary path: imagecodecs (OpenJPEG, C-level decode). Only the
        # 8-bit / uint8 case is taken — uint16 results need explicit
        # endian handling to match PDF's MSB-first byte order, which
        # Pillow's "I;16B" mode already produces, so we defer to Pillow
        # for 16-bpc rasters and for anything imagecodecs cannot decode.
        array = None
        try:
            decoded_array = imagecodecs.jpeg2k_decode(encoded_bytes)
        except Exception:
            decoded_array = None

        if decoded_array is not None and decoded_array.dtype.itemsize == 1:
            array = decoded_array

        if array is not None:
            height, width = array.shape[0], array.shape[1]
            num_components = 1 if array.ndim == 2 else array.shape[2]
            bpc = 8
            samples = array.tobytes()
        else:
            # Fallback path — Pillow's OpenJPEG plugin. Covers 16-bpc
            # grayscale (where Pillow's "I;16B" mode delivers PDF-correct
            # big-endian bytes) and any variant imagecodecs declines.
            try:
                with Image.open(io.BytesIO(encoded_bytes)) as image:
                    image.load()
                    samples = image.tobytes()
                    width, height = image.size
                    mode = image.mode
                    bands = image.getbands()
            except Exception as exc:
                raise OSError(f"JPXDecode: OpenJPEG decode failed: {exc}") from exc

            # Pillow modes → component count + bits-per-component:
            #   "1"     → 1 component, 1 bpc (rare for JPX, but pad to 8)
            #   "L"     → 1 component, 8 bpc (DeviceGray)
            #   "I;16*" → 1 component, 16 bpc (DeviceGray, high-precision)
            #   "RGB"   → 3 components, 8 bpc (DeviceRGB)
            #   "RGBA"  → 4 components, 8 bpc (DeviceRGB + alpha)
            #   "CMYK"  → 4 components, 8 bpc (DeviceCMYK)
            num_components, bpc = _mode_components_and_bpc(mode, bands)

        bytes_written = decoded.write(samples)

        out_params.set_int("Width", width)
        out_params.set_int("Height", height)
        out_params.set_int("BitsPerComponent", bpc)
        out_params.set_int("ColorComponents", num_components)

        # Per ISO 32000-1 §8.9.5.1 Note 5: "Decode shall be ignored,
        # except in the case where the image is treated as a mask."
        # Upstream JPXFilter clears the entry post-decode so downstream
        # colorspace handling doesn't double-apply the linear remap.
        if not out_params.get_boolean("ImageMask", False):
            out_params.remove_item("Decode")

        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        """Encode a raw raster as a JPEG 2000 (JP2) codestream.

        ``raw`` carries the uncompressed sample bytes in PDF row-major,
        component-interleaved order. ``parameters`` is the *stream
        dictionary* and must supply ``/Width``, ``/Height``,
        ``/BitsPerComponent`` and either ``/ColorComponents`` (the
        upstream-canonical key set by :meth:`decode`) or be sized so
        that the byte count uniquely determines the component count.

        Unlike the Java upstream which has no JPEG 2000 encoder in its
        standard library, Pillow's OpenJPEG bridge can produce a JP2
        stream — we route through that to avoid leaving callers without
        a writer.
        """
        if parameters is None:
            raise OSError(
                "JPXDecode.encode: parameters are required "
                "(need /Width, /Height, /BitsPerComponent)"
            )

        width = parameters.get_int("Width", 0)
        height = parameters.get_int("Height", 0)
        bpc = parameters.get_int("BitsPerComponent", 8)
        if width <= 0 or height <= 0:
            raise OSError(
                f"JPXDecode.encode: /Width and /Height must be positive "
                f"(got width={width}, height={height})"
            )
        if bpc not in (8, 16):
            # OpenJPEG supports arbitrary precisions up to 16 bpc, but
            # Pillow's plugin only round-trips 8- and 16-bpc rasters.
            raise OSError(
                f"JPXDecode.encode: unsupported /BitsPerComponent {bpc} "
                f"(only 8 and 16 are supported)"
            )

        raw_bytes = raw.read()
        bytes_per_sample = bpc // 8
        pixels = width * height
        # pragma: no cover — guarded above (positive w/h + bpc∈{8,16}).
        if pixels == 0 or bytes_per_sample == 0:  # pragma: no cover
            raise OSError("JPXDecode.encode: degenerate raster")

        num_components = parameters.get_int("ColorComponents", 0)
        if num_components <= 0:
            # Infer from the raw byte count when the dictionary doesn't
            # carry the helper entry our own decoder writes.
            if len(raw_bytes) % (pixels * bytes_per_sample) != 0:
                raise OSError(
                    f"JPXDecode.encode: cannot infer component count "
                    f"(raw length {len(raw_bytes)} not divisible by "
                    f"{pixels * bytes_per_sample})"
                )
            num_components = len(raw_bytes) // (pixels * bytes_per_sample)

        expected = pixels * num_components * bytes_per_sample
        if len(raw_bytes) < expected:
            raise OSError(
                f"JPXDecode.encode: raw raster too short "
                f"({len(raw_bytes)} bytes, need {expected})"
            )
        # Trim any trailing padding so Pillow's frombytes sees an
        # exactly-sized buffer.
        raw_bytes = raw_bytes[:expected]

        mode = _encode_mode_for(num_components, bpc)

        try:
            image = Image.frombytes(mode, (width, height), raw_bytes)
            buf = io.BytesIO()
            image.save(buf, format="JPEG2000")
        except Exception as exc:
            raise OSError(f"JPXDecode.encode: OpenJPEG encode failed: {exc}") from exc

        encoded.write(buf.getvalue())


FilterFactory.register("JPXDecode", JPXDecode())
