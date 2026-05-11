"""Interned one- and two-byte CMap mapping strings.

Mirrors ``org.apache.fontbox.cmap.CMapStrings`` (PDFBox 3.0,
``fontbox/src/main/java/org/apache/fontbox/cmap/CMapStrings.java``).

Upstream eagerly builds 65 792 strings (one per 1- or 2-byte sequence) at
class-load time. We do the same lazily on first import so callers can
``CMapStrings.get_mapping(b"\\x00\\x41")`` and receive ``"A"``.
"""

from __future__ import annotations


def _build_tables() -> tuple[list[str], list[str], list[int], list[bytes], list[bytes]]:
    two_byte_mappings: list[str] = []
    two_byte_values: list[bytes] = []
    index_values: list[int] = []
    for i in range(256):
        for j in range(256):
            data = bytes([i, j])
            # Java's ``new String(bytes, UTF_16BE)`` substitutes the
            # replacement character for an invalid surrogate; mirror that.
            two_byte_mappings.append(data.decode("utf-16-be", errors="replace"))
            two_byte_values.append(data)
            index_values.append(i * 256 + j)
    one_byte_mappings: list[str] = []
    one_byte_values: list[bytes] = []
    for i in range(256):
        data = bytes([i])
        one_byte_mappings.append(data.decode("iso-8859-1"))
        one_byte_values.append(data)
    return (
        two_byte_mappings,
        one_byte_mappings,
        index_values,
        one_byte_values,
        two_byte_values,
    )


_TWO_BYTE_MAPPINGS, _ONE_BYTE_MAPPINGS, _INDEX_VALUES, _ONE_BYTE_VALUES, _TWO_BYTE_VALUES = (
    _build_tables()
)


def _to_int(data: bytes | bytearray) -> int:
    value = 0
    for b in data:
        value = value << 8 | (b & 0xFF)
    return value


class CMapStrings:
    """Static-only string-interning helper."""

    def __init__(self) -> None:  # pragma: no cover
        raise TypeError("CMapStrings is a utility class")

    @staticmethod
    def get_mapping(data: bytes | bytearray) -> str | None:
        """Return the cached string for a 1- or 2-byte sequence."""
        if len(data) > 2 or len(data) == 0:
            return None
        if len(data) == 1:
            return _ONE_BYTE_MAPPINGS[_to_int(data)]
        return _TWO_BYTE_MAPPINGS[_to_int(data)]

    @staticmethod
    def get_index_value(data: bytes | bytearray) -> int | None:
        """Return the cached integer index for a 1- or 2-byte sequence."""
        if len(data) > 2 or len(data) == 0:
            return None
        return _INDEX_VALUES[_to_int(data)]

    @staticmethod
    def get_byte_value(data: bytes | bytearray) -> bytes | None:
        """Return the interned ``bytes`` instance for a 1- or 2-byte sequence."""
        if len(data) > 2 or len(data) == 0:
            return None
        if len(data) == 1:
            return _ONE_BYTE_VALUES[_to_int(data)]
        return _TWO_BYTE_VALUES[_to_int(data)]

    @staticmethod
    def fill_mappings() -> None:
        """Mirror of upstream's private ``fillMappings``.

        Upstream pre-fills the 1- and 2-byte interned-string tables at
        class load time. We build them eagerly at module import via
        ``_build_tables`` — this method is a no-op preserved for parity.
        """
        return None


__all__ = ["CMapStrings"]
