from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from pypdfbox.cos import COSArray, COSDictionary

from .decode_result import DecodeResult


class Filter(ABC):
    """
    Abstract PDF stream filter per ISO 32000-1 §7.4.

    Implementations decode an encoded byte stream into raw bytes and
    encode raw bytes back into the encoded form. The ``parameters``
    argument carries the stream's ``/DecodeParms`` (possibly indexed
    into via ``index`` when the stream has a chain of filters with a
    parallel array of decode-parameter dictionaries).

    Mirrors `org.apache.pdfbox.filter.Filter`.
    """

    @abstractmethod
    def decode(
        self,
        encoded: BinaryIO,
        decoded: BinaryIO,
        parameters: COSDictionary | None = None,
        index: int = 0,
    ) -> DecodeResult:
        """Read encoded bytes from ``encoded``, write decoded bytes to
        ``decoded``. Returns a ``DecodeResult`` whose ``parameters`` may
        be the (possibly updated) input dictionary."""

    @abstractmethod
    def encode(
        self,
        raw: BinaryIO,
        encoded: BinaryIO,
        parameters: COSDictionary | None = None,
    ) -> None:
        """Read raw bytes from ``raw``, write encoded bytes to ``encoded``."""

    # ------------------------------------------------------------------
    # Upstream parity helpers (mirror ``org.apache.pdfbox.filter.Filter``).
    # ------------------------------------------------------------------

    @staticmethod
    def decode_result(
        parameters: COSDictionary | None = None,
        decoded_byte_count: int = 0,
    ) -> DecodeResult:
        """Convenience constructor for a ``DecodeResult``.

        Mirrors ``org.apache.pdfbox.filter.Filter#createDecodeResult``
        in spirit — concrete filters use this to return a result
        carrying the (possibly mutated) parameters dictionary along
        with the count of bytes written to the decoded sink.
        """
        params = parameters if parameters is not None else COSDictionary()
        return DecodeResult(parameters=params, bytes_written=decoded_byte_count)

    @staticmethod
    def get_decode_params(
        parameters: COSDictionary | None,
        index: int,
    ) -> COSDictionary:
        """Resolve effective ``/DecodeParms`` for the filter at ``index``.

        PDF allows ``/DecodeParms`` (or its abbreviation ``/DP``) to be
        either a single dictionary — when the stream has one filter —
        or an array parallel to ``/Filter``. Missing entries return an
        empty ``COSDictionary``.

        Mirrors ``org.apache.pdfbox.filter.Filter#getDecodeParams``.
        """
        if parameters is None:
            return COSDictionary()
        for key in ("DecodeParms", "DP"):
            params = parameters.get_dictionary_object(key)
            if isinstance(params, COSDictionary):
                return params
            if isinstance(params, COSArray):
                try:
                    entry = params.get(index)
                except Exception:
                    entry = None
                if isinstance(entry, COSDictionary):
                    return entry
                return COSDictionary()
        return COSDictionary()

    def is_decompression_input_size_known(self) -> bool:
        """Whether the decompressed size of the input is known up front.

        Mirrors ``org.apache.pdfbox.filter.Filter#isDecompressionInputSizeKnown``.
        Defaults to ``True``; filters that may consume more bytes than
        the stream length advertises (notably ``ASCII85Decode`` and
        ``ASCIIHexDecode`` which can pad/ignore whitespace) override to
        ``False``.
        """
        return True
