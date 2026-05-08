from __future__ import annotations

import zlib
from typing import BinaryIO

from pypdfbox.cos import COSArray, COSDictionary

from ._predictor import predict, unpredict
from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory

_RAW_DEFLATE_FALLBACK_ERRORS = (
    "incorrect header check",
    "unknown compression method",
)


def _get_decode_params(parameters: COSDictionary | None, index: int) -> COSDictionary:
    """Resolve Flate predictor params from stream-level or direct dictionaries."""
    if parameters is None:
        return COSDictionary()
    for key in ("DecodeParms", "DP"):
        params = parameters.get_dictionary_object(key)
        if isinstance(params, COSDictionary):
            return params
        if isinstance(params, COSArray):
            try:
                entry = params.get_object(index)
            except Exception:
                entry = None
            if isinstance(entry, COSDictionary):
                return entry
            return COSDictionary()
    return parameters


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
        raw = encoded.read()
        try:
            inflated = zlib.decompress(raw)
        except zlib.error as exc:
            if any(message in str(exc) for message in _RAW_DEFLATE_FALLBACK_ERRORS):
                # Be tolerant of malformed PDFs that store raw deflate
                # bytes without the zlib wrapper normally required by
                # /FlateDecode, but keep checksum/truncation failures strict.
                try:
                    inflated = zlib.decompress(raw, wbits=-zlib.MAX_WBITS)
                except zlib.error as raw_exc:
                    raise OSError(f"FlateDecode: {raw_exc}") from raw_exc
            else:
                # Surface decompression failures (truncated streams, bad
                # checksums, etc.) as ``OSError`` so callers can rely on
                # one I/O exception type per the Filter contract.
                raise OSError(f"FlateDecode: {exc}") from exc

        decode_params = _get_decode_params(parameters, index)
        predictor = decode_params.get_int("Predictor", 1)
        if predictor > 1:
            columns = decode_params.get_int("Columns", 1)
            colors = decode_params.get_int("Colors", 1)
            bits_per_component = decode_params.get_int("BitsPerComponent", 8)
            try:
                inflated = unpredict(inflated, predictor, columns, colors, bits_per_component)
            except OSError as exc:
                raise OSError(f"FlateDecode: {exc}") from exc

        bytes_written = decoded.write(inflated)
        flush = getattr(decoded, "flush", None)
        if callable(flush):
            flush()
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
        # Honour the upstream compression-level configuration (Java's
        # ``-Dorg.apache.pdfbox.filter.deflatelevel=...`` exposed as the
        # ``SYSPROP_DEFLATELEVEL`` env var). ``-1`` means zlib default.
        level = Filter.get_compression_level()
        encoded.write(zlib.compress(data, level))
        flush = getattr(encoded, "flush", None)
        if callable(flush):
            flush()


# Register both the long name and (implicitly via the factory's
# abbreviation map) the short ``/Fl`` form.
FilterFactory.register("FlateDecode", FlateDecode())
