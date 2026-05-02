from __future__ import annotations


def _to_int(data: bytes | bytearray | memoryview, data_len: int | None = None) -> int:
    """Big-endian byte sequence to int. Mirrors ``CMap.toInt`` upstream."""
    if data_len is None:
        data_len = len(data)
    code = 0
    for i in range(data_len):
        code = (code << 8) | (data[i] & 0xFF)
    return code


class CIDRange:
    """
    Range of contiguous CIDs between two character codes.

    Mirrors ``org.apache.fontbox.cmap.CIDRange``. Upstream this class is
    package-private; pypdfbox exposes it publicly so callers and tests can
    construct typed CID ranges directly.
    """

    __slots__ = ("_from", "_to", "_unicode", "_code_length")

    def __init__(self, frm: int, to: int, unicode_: int, code_length: int) -> None:
        """
        Build a CID range.

        :param frm: start value of the code range (inclusive).
        :param to: end value of the code range (inclusive).
        :param unicode_: starting CID value mapped to ``frm``.
        :param code_length: byte length of CID input codes.
        """
        self._from = frm
        self._to = to
        self._unicode = unicode_
        self._code_length = code_length

    # ---------- accessors ----------

    def get_code_length(self) -> int:
        """Byte length of the codes covered by this range."""
        return self._code_length

    # ---------- mapping ----------

    def map_bytes(self, data: bytes | bytearray | memoryview) -> int:
        """
        Map raw input code bytes to the corresponding CID.

        Returns ``-1`` when the byte length differs from this range's
        ``code_length`` or the value lies outside ``[frm, to]``.
        """
        view = bytes(data)
        if len(view) == self._code_length:
            ch = _to_int(view)
            if self._from <= ch <= self._to:
                return self._unicode + (ch - self._from)
        return -1

    def map_int(self, code: int, length: int) -> int:
        """
        Map an integer code (with explicit byte length) to its CID.

        Returns ``-1`` if ``length`` does not match ``code_length`` or
        ``code`` lies outside ``[frm, to]``.
        """
        if length == self._code_length and self._from <= code <= self._to:
            return self._unicode + (code - self._from)
        return -1

    def unmap(self, code: int) -> int:
        """
        Map a CID back to its source code value.

        Returns ``-1`` when ``code`` lies outside the CID range covered
        by this entry.
        """
        if self._unicode <= code <= self._unicode + (self._to - self._from):
            return self._from + (code - self._unicode)
        return -1

    # ---------- coalescing ----------

    def extend(self, new_from: int, new_to: int, new_cid: int, length: int) -> bool:
        """
        Extend this range in-place if the given values are a contiguous
        continuation of it. Returns ``True`` on success.
        """
        if (
            self._code_length == length
            and new_from == self._to + 1
            and new_cid == self._unicode + self._to - self._from + 1
        ):
            self._to = new_to
            return True
        return False

    # ---------- dunder helpers ----------

    def __repr__(self) -> str:
        return (
            f"CIDRange(from={self._from}, to={self._to}, "
            f"unicode={self._unicode}, code_length={self._code_length})"
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CIDRange):
            return NotImplemented
        return (
            self._from == other._from
            and self._to == other._to
            and self._unicode == other._unicode
            and self._code_length == other._code_length
        )

    def __hash__(self) -> int:
        return hash((self._from, self._to, self._unicode, self._code_length))
