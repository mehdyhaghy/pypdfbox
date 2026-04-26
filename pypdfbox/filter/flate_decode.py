from __future__ import annotations

import zlib
from typing import BinaryIO

from pypdfbox.cos import COSDictionary

from ._predictor import predict, unpredict
from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory


class FlateDecode(Filter):
    """
    ``/FlateDecode`` filter (ISO 32000-1 §7.4.4).

    Thin adapter over :mod:`zlib` for the deflate/inflate primitives;
    the post-decompression PNG/TIFF predictor (un)filtering (§7.4.4.4)
    lives in :mod:`pypdfbox.filter._predictor` and is shared with
    :class:`LZWDecode`.

    Mirrors `org.apache.pdfbox.filter.FlateFilter`.
    """

    # ---------- public API ----------

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        try:
            inflated = zlib.decompress(encoded.read())
        except zlib.error as exc:
            # Surface decompression failures (truncated streams, bad
            # checksums, etc.) as ``OSError`` so callers can rely on
            # one I/O exception type per the Filter contract.
            raise OSError(f"FlateDecode: {exc}") from exc

        predictor = parameters.get_int("Predictor", 1) if parameters is not None else 1
        if predictor > 1:
            assert parameters is not None  # narrows for mypy
            columns = parameters.get_int("Columns", 1)
            colors = parameters.get_int("Colors", 1)
            bits_per_component = parameters.get_int("BitsPerComponent", 8)
            try:
                inflated = unpredict(inflated, predictor, columns, colors, bits_per_component)
            except OSError as exc:
                raise OSError(f"FlateDecode: {exc}") from exc

        bytes_written = decoded.write(inflated)
        out_params = parameters if parameters is not None else COSDictionary()
        return DecodeResult(parameters=out_params, bytes_written=bytes_written)

    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        data = raw.read()
        if parameters is not None:
            predictor = parameters.get_int("Predictor", 1)
            if predictor > 1:
                columns = parameters.get_int("Columns", 1)
                colors = parameters.get_int("Colors", 1)
                bits_per_component = parameters.get_int("BitsPerComponent", 8)
                try:
                    data = predict(data, predictor, columns, colors, bits_per_component)
                except OSError as exc:
                    raise OSError(f"FlateDecode: {exc}") from exc
        encoded.write(zlib.compress(data))


# Register both the long name and (implicitly via the factory's
# abbreviation map) the short ``/Fl`` form.
FilterFactory.register("FlateDecode", FlateDecode())
