from __future__ import annotations

import io
import zlib
from typing import BinaryIO

from pypdfbox.cos import COSArray, COSDictionary

from ._predictor import predict, unpredict
from .decode_result import DecodeResult
from .filter import Filter
from .filter_factory import FilterFactory
from .flate_filter_decoder_stream import FlateFilterDecoderStream


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
        # Decode through ``FlateFilterDecoderStream`` (mirrors upstream's
        # ``FlateFilter.decode`` which wraps the body in this stream rather
        # than calling a one-shot inflate). The wrapper skips the 2-byte
        # zlib header, uses a nowrap ``Inflater``, and on a truncated /
        # corrupt body (``DataFormatException``) logs a warning and yields
        # whatever was already inflated instead of raising — PDFBOX-1232.
        # This is the lenient partial-inflate contract a one-shot
        # ``zlib.decompress`` cannot reproduce (it raises Error -5 on a
        # missing Z_STREAM_END / truncation).
        inflated = FlateFilterDecoderStream(io.BytesIO(raw)).read()
        if not inflated and len(raw) > 2:
            # Documented divergence (kept from the original port): a body
            # that is raw deflate with NO zlib header makes the nowrap
            # inflate fail on the first block, so the decoder stream yields
            # zero bytes (this is exactly what PDFBox does too — it logs and
            # returns empty). pypdfbox is deliberately more lenient: retry a
            # bare raw-deflate inflate so malformed PDFs that omit the zlib
            # wrapper still recover their payload. A genuinely empty stream
            # (decoded to b"") leaves this retry a no-op. See CHANGES.md.
            try:
                inflated = zlib.decompress(raw, wbits=-zlib.MAX_WBITS)
            except zlib.error:
                inflated = b""

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
