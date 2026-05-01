from __future__ import annotations

import io
from typing import BinaryIO

from PIL import Image

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory


class JPXDecode(Filter):
    """``/JPXDecode`` filter (ISO 32000-1 §7.4.9).

    Decodes a JPEG 2000 (JP2 / JPX / raw J2K) codestream by delegating to
    Pillow's OpenJPEG-backed ``Jpeg2KImagePlugin``. Decoder-only — PDF
    rarely *encodes* JPEG 2000 from raw samples on the write side and we
    have no producer use case yet.

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
        out_params = parameters if parameters is not None else COSDictionary()
        if not encoded_bytes:
            return DecodeResult(parameters=out_params, bytes_written=0)

        try:
            with Image.open(io.BytesIO(encoded_bytes)) as image:
                image.load()
                samples = image.tobytes()
                width, height = image.size
                mode = image.mode
        except Exception as exc:
            raise OSError(f"JPXDecode: OpenJPEG decode failed: {exc}") from exc

        # Pillow modes → component count + bits-per-component:
        #   "1"     → 1 component, 1 bpc (rare for JPX, but pad to 8)
        #   "L"     → 1 component, 8 bpc (DeviceGray)
        #   "I;16"  → 1 component, 16 bpc (DeviceGray, high-precision)
        #   "RGB"   → 3 components, 8 bpc (DeviceRGB)
        #   "RGBA"  → 4 components, 8 bpc (DeviceRGB + alpha)
        #   "CMYK"  → 4 components, 8 bpc (DeviceCMYK)
        if mode == "L":
            num_components, bpc = 1, 8
        elif mode == "I;16":
            num_components, bpc = 1, 16
        elif mode == "RGB":
            num_components, bpc = 3, 8
        elif mode == "RGBA":
            num_components, bpc = 4, 8
        elif mode == "CMYK":
            num_components, bpc = 4, 8
        elif mode == "1":
            num_components, bpc = 1, 1
        else:
            num_components, bpc = len(image.getbands()), 8

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
        raise NotImplementedError(
            "JPXDecode.encode is not implemented (decode-only)"
        )


FilterFactory.register("JPXDecode", JPXDecode())
