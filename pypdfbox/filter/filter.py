from __future__ import annotations

from abc import ABC, abstractmethod
from typing import BinaryIO

from pypdfbox.cos import COSDictionary

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
