from __future__ import annotations


class BFCharEntry:
    """
    A single ``bfchar`` mapping from a ToUnicode CMap.

    Upstream Apache PDFBox does not expose a ``BFCharEntry`` class — the
    parser inlines ``bfchar`` triples directly into
    ``CMap.addCharMapping(byte[], String)``. pypdfbox adds this typed value
    object so tools that build CMaps programmatically (font subsetters,
    ToUnicode emitters) can carry around a single mapping without juggling
    raw tuples.

    A ``BFCharEntry`` is immutable: the input code bytes and Unicode
    target are captured at construction time and never mutated.
    """

    __slots__ = ("_code", "_unicode")

    def __init__(
        self,
        code: bytes | bytearray | memoryview,
        unicode_str: str,
    ) -> None:
        """
        :param code: raw input character code bytes (1-4 bytes).
        :param unicode_str: Unicode string the code maps to.
        :raises ValueError: if ``code`` is empty or longer than 4 bytes.
        """
        data = bytes(code)
        if not 1 <= len(data) <= 4:
            raise ValueError(
                f"bfchar input code must be 1-4 bytes long, got {len(data)}"
            )
        self._code = data
        self._unicode = unicode_str

    # ---------- accessors ----------

    def get_code(self) -> bytes:
        """Return the raw code bytes for this mapping."""
        return self._code

    def get_unicode(self) -> str:
        """Return the Unicode target string."""
        return self._unicode

    def get_code_length(self) -> int:
        """Byte length of the input code."""
        return len(self._code)

    # ---------- equality / hashing ----------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BFCharEntry):
            return NotImplemented
        return self._code == other._code and self._unicode == other._unicode

    def __hash__(self) -> int:
        return hash((self._code, self._unicode))

    def __repr__(self) -> str:
        hex_code = self._code.hex().upper()
        return f"BFCharEntry(<{hex_code}> -> {self._unicode!r})"
