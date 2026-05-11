"""Predictor — public mirror of ``org.apache.pdfbox.filter.Predictor``.

Container class for the PNG / TIFF predictor helpers used by
``/FlateDecode`` and ``/LZWDecode`` per ISO 32000-1 §7.4.4.4. Upstream
PDFBox keeps the helpers as ``static`` methods on a ``final class``; the
Python port wraps the same helpers (already implemented in
:mod:`pypdfbox.filter._predictor`) under a class namespace so callers can
write ``Predictor.calculate_row_length(...)`` exactly like Java.

Library-first: ``calculate_row_length`` is one expression and
``decode_predictor_row`` is a small per-row state machine — these are
not "generic concerns" any third-party library offers, so they stay in
``_predictor`` and are re-exported here.
"""

from __future__ import annotations

from typing import BinaryIO

from pypdfbox.cos import COSDictionary, COSName

from ._predictor import calculate_row_length, decode_predictor_row
from .predictor_output_stream import PredictorOutputStream


class Predictor:
    """Helper class to contain predictor decoding used by Flate and LZW.

    Mirrors ``org.apache.pdfbox.filter.Predictor``. All members are
    static — the class is never instantiated; it acts as a namespace
    just like the upstream ``final class``.
    """

    def __init__(self) -> None:
        # Upstream's private no-arg constructor is a no-op; mirroring it
        # makes ``Predictor()`` safe even though nothing useful happens.
        return

    # ------------------------------------------------------------------
    # Static helpers
    # ------------------------------------------------------------------

    @staticmethod
    def decode_predictor_row(
        predictor: int,
        colors: int,
        bits_per_component: int,
        columns: int,
        actline: bytearray,
        lastline: bytes | bytearray,
    ) -> None:
        """Decode a single predictor-encoded row in place.

        Mirrors ``Predictor#decodePredictorRow`` (Java).
        """
        decode_predictor_row(
            predictor, colors, bits_per_component, columns, actline, lastline
        )

    @staticmethod
    def calculate_row_length(colors: int, bits_per_component: int, columns: int) -> int:
        """Return the width of one scanline in whole bytes (rounded up).

        Mirrors ``Predictor#calculateRowLength`` (Java).
        """
        return calculate_row_length(colors, bits_per_component, columns)

    @staticmethod
    def get_bit_seq(by: int, start_bit: int, bit_size: int) -> int:
        """Extract a bit window from a byte.

        Mirrors ``Predictor#getBitSeq`` (Java).
        """
        mask = (1 << bit_size) - 1
        # Python ints are unbounded; coerce ``by`` to its 0..255 view to
        # match the Java ``byte``-promotion semantics.
        return ((by & 0xFF) >> start_bit) & mask

    @staticmethod
    def calc_set_bit_seq(by: int, start_bit: int, bit_size: int, val: int) -> int:
        """Splice ``val`` into ``by`` at ``start_bit`` and return the result.

        Mirrors ``Predictor#calcSetBitSeq`` (Java).
        """
        mask = (1 << bit_size) - 1
        truncated_val = val & mask
        mask_shift = ~(mask << start_bit) & 0xFF
        return ((by & 0xFF) & mask_shift) | (truncated_val << start_bit)

    @staticmethod
    def wrap_predictor(out: BinaryIO, decode_params: COSDictionary) -> BinaryIO:
        """Wrap ``out`` in a :class:`PredictorOutputStream` when the decode
        parameters declare a non-trivial predictor; otherwise return ``out``.

        Mirrors ``Predictor#wrapPredictor`` (Java).
        """
        predictor = decode_params.get_int(COSName.get_pdf_name("Predictor").get_name(), 1)
        if predictor > 1:
            colors = min(
                decode_params.get_int(COSName.get_pdf_name("Colors").get_name(), 1),
                32,
            )
            bits_per_component = decode_params.get_int(
                COSName.get_pdf_name("BitsPerComponent").get_name(), 8
            )
            columns = decode_params.get_int(
                COSName.get_pdf_name("Columns").get_name(), 1
            )
            return PredictorOutputStream(
                out, predictor, colors, bits_per_component, columns
            )
        return out
