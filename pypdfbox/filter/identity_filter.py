from __future__ import annotations

from typing import BinaryIO

from pypdfbox.cos import COSDictionary
from pypdfbox.io.io_utils import copy

from .decode_result import DecodeResult
from .filter import Filter


class IdentityFilter(Filter):
    """``Identity`` filter (ISO 32000-1 §7.6.5, Table 26).

    Pass-through filter: ``decode`` and ``encode`` both copy the input
    byte-for-byte to the output without any transformation. Used by the
    ``/Crypt`` filter as the default identity crypt sub-filter when no
    ``/Name`` is specified or when ``/Identity`` is named explicitly.

    Mirrors `org.apache.pdfbox.filter.IdentityFilter`. Upstream marks the
    class package-private (no public registration in ``FilterFactory``)
    because callers reach it only through the ``CryptFilter`` indirection
    and via ``new IdentityFilter()``; we follow the same pattern and do
    not register it under any short or long PDF filter name.
    """

    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        bytes_written = copy(encoded, decoded)
        # Mirror upstream's ``decoded.flush()`` so callers writing to a
        # buffered sink see the bytes immediately. ``BytesIO`` has a
        # no-op ``flush``; on real file handles this matters.
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
        copy(raw, encoded)
        flush = getattr(encoded, "flush", None)
        if callable(flush):
            flush()
