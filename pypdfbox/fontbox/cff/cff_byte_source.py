from __future__ import annotations

from .byte_source import ByteSource


class CFFBytesource(ByteSource):
    """Concrete :class:`ByteSource` over a CFF font's underlying byte array.

    Mirrors the private static class
    ``org.apache.fontbox.cff.CFFParser.CFFBytesource`` (note the lowercase
    ``s`` — preserved verbatim from upstream).

    Allows bytes to be re-read later by ``CFFParser`` — the parser holds
    on to a ``ByteSource`` after the first parse so it can rebuild the
    font (e.g. for embedded subsetting or fallback re-parsing) without
    requiring the caller to keep a reference to the original buffer.
    """

    def __init__(self, data: bytes | bytearray | memoryview) -> None:
        # Upstream stores the raw byte[] directly; we coerce to immutable
        # ``bytes`` so subsequent in-place mutations on a passed-in
        # bytearray cannot corrupt parser state.
        self._bytes: bytes = bytes(data)

    def get_bytes(self) -> bytes:
        return self._bytes
