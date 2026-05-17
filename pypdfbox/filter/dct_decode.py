from __future__ import annotations

import io
from typing import BinaryIO

import imagecodecs
from PIL import Image

from pypdfbox.cos import COSDictionary

from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory


class DCTDecode(Filter):
    """``/DCTDecode`` filter (ISO 32000-1 §7.4.8).

    Decodes baseline/progressive JPEG image streams by delegating to
    :func:`imagecodecs.jpeg8_decode`, falling back to Pillow's JPEG codec
    for variants imagecodecs declines (e.g. some Adobe-marker or unusual
    CMYK encodings). Geometry and component metadata are surfaced through
    ``DecodeResult.parameters`` so callers can fill missing image-dictionary
    entries, matching the JPX/JBIG2 filter pattern used locally.

    Why imagecodecs first: the bundled JPEG codec is libjpeg-turbo
    (BSD-style, same as Pillow's internal codec when built against
    libjpeg-turbo) but exposed via a thin C-level API — typically 2-4x
    faster decode for large rasters because no Pillow ``Image`` object is
    materialised. CMYK JPEGs (which Pillow has historically been finicky
    about) also round-trip more cleanly. The Pillow fallback preserves
    backwards compatibility for any encoder variant imagecodecs refuses.

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
        if encoded_bytes.startswith(b"\n"):
            encoded_bytes = encoded_bytes[1:]

        samples: bytes
        width: int
        height: int
        num_components: int
        bpc: int

        # Primary path: imagecodecs (libjpeg-turbo, C-level decode).
        # Returns a numpy array shaped (H, W) for grayscale, (H, W, C) for
        # multi-component. Falls back to Pillow on any decode failure so
        # we keep coverage of Adobe-marker / progressive / unusual variants
        # the upstream JPEG codec may handle differently.
        try:
            array = imagecodecs.jpeg8_decode(encoded_bytes)
        except Exception:
            array = None

        if array is not None:
            height, width = array.shape[0], array.shape[1]
            num_components = 1 if array.ndim == 2 else array.shape[2]
            bpc = 8
            samples = array.tobytes()
        else:
            # Pillow fallback path — used when imagecodecs declines the
            # codestream (rare; e.g. some Adobe-marker variants).
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
        """``/DCTDecode`` is a decode-only filter — by upstream design.

        Mirrors ``DCTFilter.encode`` in Apache PDFBox, which raises
        ``UnsupportedOperationException`` with this same message.
        Producing a JPEG image is a higher-level concern handled by
        ``JPEGFactory`` (which composes the JPEG bytes itself via
        ImageIO and then attaches them to a ``PDImageXObject`` carrying
        the ``/DCTDecode`` filter name) rather than by the filter layer.
        This is upstream-faithful behaviour, not a pypdfbox deferral.
        """
        raise NotImplementedError(
            "DCTFilter encoding not implemented, use the JPEGFactory methods instead"
        )


FilterFactory.register("DCTDecode", DCTDecode())
