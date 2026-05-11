from __future__ import annotations

import io
from typing import TYPE_CHECKING, BinaryIO

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pypdfbox.filter.decode_result import DecodeResult
    from pypdfbox.filter.filter import Filter

    from .cos_dictionary import COSDictionary


class COSInputStream(io.IOBase):
    """An ``InputStream`` which reads from a decoded COS stream.

    Mirrors upstream ``org.apache.pdfbox.cos.COSInputStream`` (a final
    subclass of ``FilterInputStream``). Wraps the raw encoded source,
    applies the chain of decode filters, and exposes the decoded bytes
    plus per-filter :class:`DecodeResult` metadata used by repair paths.
    """

    def __init__(
        self,
        decoded: BinaryIO,
        decode_results: list[DecodeResult],
    ) -> None:
        # ``FilterInputStream``-style: wrap an underlying stream. We keep
        # the decoded buffer as our `_inner` and proxy reads to it.
        super().__init__()
        self._inner: BinaryIO = decoded
        self._decode_results: list[DecodeResult] = decode_results
        self._closed_flag: bool = False

    # ------------------------------------------------------------------
    # Factory mirroring upstream's package-private ``create`` overloads.
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        filters: Sequence[Filter],
        parameters: COSDictionary,
        encoded: BinaryIO,
        options: object | None = None,
    ) -> COSInputStream:
        """Apply ``filters`` (in order) to ``encoded`` and return a
        ``COSInputStream`` over the decoded bytes.

        Mirrors upstream ``COSInputStream.create(List<Filter>,
        COSDictionary, InputStream[, DecodeOptions])`` (Java line 49 /
        line 65). When ``filters`` is empty the stream is returned
        verbatim with an empty result list.
        """
        # Local import to avoid module cycle with the filter package.
        from pypdfbox.filter.filter import Filter  # noqa: PLC0415

        if not filters:
            return cls(encoded, [])

        from pypdfbox.filter.decode_result import DecodeResult  # noqa: F401, PLC0415

        results: list[DecodeResult] = []
        decoded = Filter.decode_chain(
            encoded, list(filters), parameters, options, results
        )
        return cls(decoded, results)

    # ------------------------------------------------------------------
    # IOBase / FilterInputStream-style proxy methods
    # ------------------------------------------------------------------

    def read(self, size: int = -1) -> bytes:  # type: ignore[override]
        return self._inner.read(size)

    def readinto(self, b: bytearray | memoryview) -> int:  # type: ignore[override]
        return self._inner.readinto(b)  # type: ignore[union-attr]

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return getattr(self._inner, "seekable", lambda: False)()

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:  # type: ignore[override]
        return self._inner.seek(offset, whence)

    def tell(self) -> int:
        return self._inner.tell()

    def close(self) -> None:  # type: ignore[override]
        if self._closed_flag:
            return
        self._closed_flag = True
        try:
            self._inner.close()
        finally:
            super().close()

    # ------------------------------------------------------------------
    # Upstream-specific accessor
    # ------------------------------------------------------------------

    def get_decode_result(self) -> DecodeResult:
        """Return the last filter's :class:`DecodeResult`. Used by repair
        mechanisms that need the parameter dictionary as actually
        consumed.

        Mirrors upstream ``COSInputStream.getDecodeResult`` (Java line 96).
        """
        from pypdfbox.filter.decode_result import DecodeResult  # noqa: PLC0415

        if not self._decode_results:
            return DecodeResult.create_default()
        return self._decode_results[-1]
