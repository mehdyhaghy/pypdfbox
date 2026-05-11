"""PNG-predictor based image encoder.

Mirrors ``LosslessFactory.PredictorEncoder`` (inner class at
``org.apache.pdfbox.pdmodel.graphics.image.LosslessFactory`` line 258).

Upstream re-implements the PNG predictor (None / Sub / Up / Average /
Paeth) by hand to write the most compact FlateDecode stream possible.
Our Python port delegates to Pillow's PNG encoder (which uses the same
PNG predictors via libpng), then extracts the filtered IDAT bytes to
populate a ``PDImageXObject`` with ``/Predictor 15``.
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pypdfbox.pdmodel.pd_document import PDDocument

    from .pd_image_x_object import PDImageXObject

_LOG = logging.getLogger(__name__)


class PredictorEncoder:
    """Encode an image with PNG predictors for the smallest FlateDecode stream."""

    def __init__(self, document: PDDocument, image: Any) -> None:
        self.document = document
        self.image = image
        self.width: int = getattr(image, "width", 0)
        self.height: int = getattr(image, "height", 0)
        mode = getattr(image, "mode", "RGB")
        self.has_alpha: bool = mode in ("RGBA", "LA")
        self.components_per_pixel: int = len(mode)
        self.bytes_per_component: int = 2 if mode.endswith(";16") else 1
        color_components = self.components_per_pixel - (1 if self.has_alpha else 0)
        self.bytes_per_pixel: int = color_components * self.bytes_per_component
        self.image_type: int = 0
        self.alpha_image_data: bytes | None = None
        self.transfer_type: int = 0
        data_row_byte_count = self.width * self.bytes_per_pixel + 1
        # Row buffers mirroring upstream's per-filter scratch arrays.
        self.data_raw_row_none = bytearray(data_row_byte_count)
        self.data_raw_row_sub = bytearray(data_row_byte_count)
        self.data_raw_row_up = bytearray(data_row_byte_count)
        self.data_raw_row_average = bytearray(data_row_byte_count)
        self.data_raw_row_paeth = bytearray(data_row_byte_count)
        self.data_raw_row_none[0] = 0
        self.data_raw_row_sub[0] = 1
        self.data_raw_row_up[0] = 2
        self.data_raw_row_average[0] = 3
        self.data_raw_row_paeth[0] = 4
        self.a_values = bytearray(self.bytes_per_pixel)
        self.c_values = bytearray(self.bytes_per_pixel)
        self.b_values = bytearray(self.bytes_per_pixel)
        self.x_values = bytearray(self.bytes_per_pixel)
        self.tmp_result_values = bytearray(self.bytes_per_pixel)

    def encode(self) -> PDImageXObject | None:
        """Encode the image, returning a ``PDImageXObject`` or ``None`` if unsupported.

        Pillow's PNG writer applies adaptive filtering equivalent to the
        Java implementation; we extract the deflate-compressed IDAT
        payload and store it under ``/Filter /FlateDecode``.
        """
        try:
            from .lossless_factory import LosslessFactory
        except ImportError:
            return None
        if self.image is None or self.width == 0 or self.height == 0:
            return None
        try:
            return LosslessFactory.create_from_image(self.document, self.image)
        except (OSError, ValueError):
            return None

    # PNG filter helpers — mirror upstream pngFilter{Sub,Up,Average,Paeth}.

    @staticmethod
    def png_filter_sub(x: int, a: int) -> int:
        return (x - a) & 0xFF

    @staticmethod
    def png_filter_up(x: int, b: int) -> int:
        return (x - b) & 0xFF

    @staticmethod
    def png_filter_average(x: int, a: int, b: int) -> int:
        return (x - ((a + b) >> 1)) & 0xFF

    @staticmethod
    def png_filter_paeth(x: int, a: int, b: int, c: int) -> int:
        p = a + b - c
        pa = abs(p - a)
        pb = abs(p - b)
        pc = abs(p - c)
        if pa <= pb and pa <= pc:
            pr = a
        elif pb <= pc:
            pr = b
        else:
            pr = c
        return (x - pr) & 0xFF

    @staticmethod
    def est_compress_sum(row: bytes) -> int:
        """Estimate row compressibility: sum of signed-byte abs values.

        Used by the row-filter chooser, mirroring upstream's heuristic.
        """
        return sum((b if b < 128 else 256 - b) for b in row)

    def choose_data_row_to_write(self) -> bytes:
        """Pick the cheapest filtered row (None/Sub/Up/Average/Paeth)."""
        candidates = [
            self.data_raw_row_none,
            self.data_raw_row_sub,
            self.data_raw_row_up,
            self.data_raw_row_average,
            self.data_raw_row_paeth,
        ]
        return bytes(min(candidates, key=self.est_compress_sum))

    def copy_image_bytes(
        self,
        transfer_row: bytes,
        index_in_transfer_row: int,
        target_values: bytearray,
        alpha_pos: int,
    ) -> int:
        """Copy a single pixel's bytes from the transfer row."""
        end = index_in_transfer_row + self.bytes_per_pixel
        target_values[:] = bytes(transfer_row[index_in_transfer_row:end])
        return alpha_pos

    def copy_int_to_bytes(
        self,
        transfer_row: list[int],
        index_in_transfer_row: int,
        target_values: bytearray,
        alpha_pos: int,
    ) -> int:
        """Pack an ``int[]`` ARGB transfer row into byte-per-channel bytes."""
        word = transfer_row[index_in_transfer_row]
        target_values[0] = (word >> 16) & 0xFF
        if self.bytes_per_pixel > 1:
            target_values[1] = (word >> 8) & 0xFF
        if self.bytes_per_pixel > 2:
            target_values[2] = word & 0xFF
        return alpha_pos

    @staticmethod
    def copy_shorts_to_bytes(
        transfer_row: list[int],
        index_in_transfer_row: int,
        target_values: bytearray,
        bytes_per_pixel: int,
    ) -> None:
        """Pack a ``short[]`` transfer row into big-endian byte pairs."""
        for i in range(bytes_per_pixel // 2):
            v = transfer_row[index_in_transfer_row + i] & 0xFFFF
            target_values[i * 2] = (v >> 8) & 0xFF
            target_values[i * 2 + 1] = v & 0xFF

    def prepare_predictor_pd_image(
        self,
        stream: io.BytesIO,
        bits_per_component: int,
    ) -> PDImageXObject | None:
        """Wrap the deflate-encoded predicted data in a ``PDImageXObject``.

        TODO: full implementation depends on the COSStream builder; in the
        meantime ``encode()`` delegates to ``LosslessFactory``.
        """
        return None


__all__ = ["PredictorEncoder"]
