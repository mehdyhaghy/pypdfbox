"""Interned one- and two-byte CMap mapping strings.

Mirrors ``org.apache.fontbox.cmap.CMapStrings`` (PDFBox 3.0,
``fontbox/src/main/java/org/apache/fontbox/cmap/CMapStrings.java``).

Upstream eagerly builds 65 792 strings (one per 1- or 2-byte sequence) at
class-load time. We do the same lazily on first import so callers can
``CMapStrings.get_mapping(b"\\x00\\x41")`` and receive ``"A"``.
"""


def _build_tables() -> tuple[list[str], list[str], list[int], list[bytes], list[bytes]]:
    # Java's ``new String(bytes, UTF_16BE)`` maps every 2-byte code unit to
    # itself except a lone surrogate (0xD800-0xDFFF), which becomes the
    # replacement character; ``chr`` plus that substitution equals
    # ``bytes([i, j]).decode("utf-16-be", errors="replace")`` for all 65 536
    # values without paying for a per-pair codec call.
    two_byte_mappings = [chr(v) for v in range(0xD800)]
    two_byte_mappings.extend("\ufffd" for _ in range(0xD800, 0xE000))
    two_byte_mappings.extend(chr(v) for v in range(0xE000, 0x10000))
    two_byte_values = [v.to_bytes(2, "big") for v in range(0x10000)]
    index_values = list(range(0x10000))
    # ISO-8859-1 maps each byte to the code point of the same value.
    one_byte_mappings = [chr(i) for i in range(256)]
    one_byte_values = [bytes((i,)) for i in range(256)]
    return (
        two_byte_mappings,
        one_byte_mappings,
        index_values,
        one_byte_values,
        two_byte_values,
    )


_TABLE_NAMES = (
    "_TWO_BYTE_MAPPINGS",
    "_ONE_BYTE_MAPPINGS",
    "_INDEX_VALUES",
    "_ONE_BYTE_VALUES",
    "_TWO_BYTE_VALUES",
)
_tables: tuple[list[str], list[str], list[int], list[bytes], list[bytes]] | None = None


def _get_tables() -> tuple[list[str], list[str], list[int], list[bytes], list[bytes]]:
    """Build the interned tables on first use (upstream does it at class load)."""
    global _tables
    if _tables is None:
        _tables = _build_tables()
    return _tables


def __getattr__(name: str) -> object:
    # The tables used to be module globals built at import time.
    if name in _TABLE_NAMES:
        return _get_tables()[_TABLE_NAMES.index(name)]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
            return _get_tables()[1][_to_int(data)]
        return _get_tables()[0][_to_int(data)]

    @staticmethod
    def get_index_value(data: bytes | bytearray) -> int | None:
        """Return the cached integer index for a 1- or 2-byte sequence."""
        if len(data) > 2 or len(data) == 0:
            return None
        return _get_tables()[2][_to_int(data)]

    @staticmethod
    def get_byte_value(data: bytes | bytearray) -> bytes | None:
        """Return the interned ``bytes`` instance for a 1- or 2-byte sequence."""
        if len(data) > 2 or len(data) == 0:
            return None
        if len(data) == 1:
            return _get_tables()[3][_to_int(data)]
        return _get_tables()[4][_to_int(data)]

    @staticmethod
    def fill_mappings() -> None:
        """Mirror of upstream's private ``fillMappings``.

        Upstream pre-fills the 1- and 2-byte interned-string tables at
        class load time. We build them on first lookup via
        ``_build_tables``; this method is a no-op preserved for parity.
        """
        return


__all__ = ["CMapStrings"]
