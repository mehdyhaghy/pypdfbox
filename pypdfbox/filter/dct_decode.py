from __future__ import annotations

import io
from typing import BinaryIO

from PIL import Image

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory


class DCTDecode(Filter):
    """``/DCTDecode`` filter (ISO 32000-1 §7.4.8).

    Decodes baseline/progressive JPEG image streams by delegating to Pillow's
    JPEG decoder and writing the raw sample bytes. Geometry and component
    metadata are surfaced through ``DecodeResult.parameters`` so callers can
    fill missing image-dictionary entries, matching the JPX/JBIG2 filter
    pattern used locally.

    Mirrors ``org.apache.pdfbox.filter.DCTFilter``.
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
                bands = image.getbands()
        except Exception as exc:
            raise OSError(f"DCTDecode: JPEG decode failed: {exc}") from exc

        if mode == "L":
            num_components, bpc = 1, 8
        elif mode == "CMYK":
            num_components, bpc = 4, 8
        elif mode == "RGB":
            num_components, bpc = 3, 8
        else:
            num_components, bpc = len(bands), 8

        bytes_written = decoded.write(samples)

        out_params.set_int("Width", width)
        out_params.set_int("Height", height)
        out_params.set_int("BitsPerComponent", bpc)
        out_params.set_int("ColorComponents", num_components)
        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        raise NotImplementedError(
            "DCTDecode.encode is not implemented (decode-only)"
        )


FilterFactory.register("DCTDecode", DCTDecode())
