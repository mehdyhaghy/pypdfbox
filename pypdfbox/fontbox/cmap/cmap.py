from __future__ import annotations

import logging
from typing import BinaryIO

from pypdfbox.io import RandomAccessRead

from .codespace_range import CodespaceRange

_log = logging.getLogger(__name__)

_SPACE = " "


class _CIDRange:
    """Range of contiguous CID values (package-private upstream)."""

    __slots__ = ("_from", "_to", "_unicode", "_code_length")

    def __init__(self, frm: int, to: int, unicode_: int, code_length: int) -> None:
        self._from = frm
        self._to = to
        self._unicode = unicode_
        self._code_length = code_length

    def get_code_length(self) -> int:
        return self._code_length

    def map_bytes(self, data: bytes) -> int:
        if len(data) == self._code_length:
            ch = _to_int(data)
            if self._from <= ch <= self._to:
                return self._unicode + (ch - self._from)
        return -1

    def map_int(self, code: int, length: int) -> int:
        if length == self._code_length and self._from <= code <= self._to:
            return self._unicode + (code - self._from)
        return -1

    def unmap(self, code: int) -> int:
        if self._unicode <= code <= self._unicode + (self._to - self._from):
            return self._from + (code - self._unicode)
        return -1

    def extend(self, new_from: int, new_to: int, new_cid: int, length: int) -> bool:
        if (
            self._code_length == length
            and new_from == self._to + 1
            and new_cid == self._unicode + self._to - self._from + 1
        ):
            self._to = new_to
            return True
        return False


def _to_int(data: bytes | bytearray | memoryview, data_len: int | None = None) -> int:
    """Big-endian byte sequence to int."""
    if data_len is None:
        data_len = len(data)
    code = 0
    for i in range(data_len):
        code = (code << 8) | (data[i] & 0xFF)
    return code


def _bytes_for_code(code: int, length: int) -> bytes:
    """Big-endian bytes representation of ``code`` with given byte length."""
    out = bytearray(length)
    for i in range(length - 1, -1, -1):
        out[i] = code & 0xFF
        code >>= 8
    return bytes(out)


class CMap:
    """
    A parsed PostScript CMap (PDF 32000-1 §9.7).

    Holds codespace ranges, code-to-CID mappings, and code-to-Unicode
    mappings. ``CMapParser`` is the standard producer; tests sometimes
    construct one directly via the ``add_*`` setters.
    """

    def __init__(self, name: str | None = None) -> None:
        self._wmode: int = 0
        self._cmap_name: str | None = name
        self._cmap_version: str | None = None
        self._cmap_type: int = -1

        self._registry: str | None = None
        self._ordering: str | None = None
        self._supplement: int = 0

        self._min_code_length: int = 4
        self._max_code_length: int = 0

        self._min_cid_length: int = 4
        self._max_cid_length: int = 0

        self._codespace_ranges: list[CodespaceRange] = []

        # Unicode mappings, partitioned by input byte length (1 / 2 / 3-4).
        self._char_to_unicode_one_byte: dict[int, str] = {}
        self._char_to_unicode_two_bytes: dict[int, str] = {}
        self._char_to_unicode_more_bytes: dict[int, str] = {}

        # CID mappings: dict-of-dicts keyed by input byte length.
        self._code_to_cid: dict[int, dict[int, int]] = {}
        self._code_to_cid_ranges: list[_CIDRange] = []

        # Inverted (Unicode -> code bytes) mapping.
        self._unicode_to_byte_codes: dict[str, bytes] = {}

        self._space_mapping: int = -1

    # ---------- introspection ----------

    def has_cid_mappings(self) -> bool:
        return bool(self._code_to_cid) or bool(self._code_to_cid_ranges)

    def has_unicode_mappings(self) -> bool:
        return (
            bool(self._char_to_unicode_one_byte)
            or bool(self._char_to_unicode_two_bytes)
            or bool(self._char_to_unicode_more_bytes)
        )

    # ---------- to_unicode ----------

    def to_unicode(self, code: int) -> str | None:
        """Return the Unicode string for the given character code, or
        ``None`` if no mapping is defined.

        This convenience overload guesses the byte length from the value:
        codes < 256 are tried as 1-byte first, then 2-byte, etc."""
        unicode_ = self._to_unicode_with_len(code, 1) if code < 256 else None
        if unicode_ is None:
            if code <= 0xFFFF:
                return self._to_unicode_with_len(code, 2)
            if code <= 0xFFFFFF:
                return self._to_unicode_with_len(code, 3)
            return self._to_unicode_with_len(code, 4)
        return unicode_

    def _to_unicode_with_len(self, code: int, length: int) -> str | None:
        if length == 1:
            return self._char_to_unicode_one_byte.get(code)
        if length == 2:
            return self._char_to_unicode_two_bytes.get(code)
        return self._char_to_unicode_more_bytes.get(code)

    def to_unicode_bytes(self, code: bytes | bytearray | memoryview) -> str | None:
        """Lookup by raw input code bytes — the unambiguous form."""
        data = bytes(code)
        return self._to_unicode_with_len(_to_int(data), len(data))

    # ---------- read_code / read_cid ----------

    def read_code(self, input_stream: RandomAccessRead | BinaryIO) -> int:
        """Read enough bytes from ``input_stream`` to match a codespace
        range and return the matched code as an int.

        Per ISO 32000-1 §9.7.6.2 — start with ``min_code_length`` bytes,
        check against codespace ranges; on failure read one more byte and
        retry, up to ``max_code_length``. On total failure, fall back to
        the first ``min_code_length`` bytes (Adobe Reader behavior)."""
        max_len = self._max_code_length
        min_len = self._min_code_length
        if max_len <= 0:
            b = self._read_one(input_stream)
            return b if b >= 0 else 0
        bytes_buf = bytearray(max_len)

        # Read the initial minCodeLength bytes.
        read = self._read_some(input_stream, bytes_buf, 0, min_len)
        if read < min_len:
            return _to_int(bytes_buf, max(read, 1)) if read > 0 else 0

        for i in range(min_len - 1, max_len):
            byte_count = i + 1
            for r in self._codespace_ranges:
                if r.is_full_match(bytes_buf, byte_count):
                    return _to_int(bytes_buf, byte_count)
            if byte_count < max_len:
                b = self._read_one(input_stream)
                if b < 0:
                    break
                bytes_buf[byte_count] = b

        if _log.isEnabledFor(logging.WARNING):
            sb = " ".join(f"0x{bytes_buf[i] & 0xFF:02X}" for i in range(max_len))
            _log.warning(
                "Invalid character code sequence %s in CMap %s",
                sb,
                self._cmap_name,
            )
        return _to_int(bytes_buf, min_len)

    @staticmethod
    def _read_one(stream: RandomAccessRead | BinaryIO) -> int:
        if isinstance(stream, RandomAccessRead):
            return stream.read()
        chunk = stream.read(1)
        if not chunk:
            return -1
        return chunk[0]

    @classmethod
    def _read_some(
        cls,
        stream: RandomAccessRead | BinaryIO,
        buf: bytearray,
        offset: int,
        length: int,
    ) -> int:
        if isinstance(stream, RandomAccessRead):
            total = 0
            while total < length:
                b = stream.read()
                if b < 0:
                    break
                buf[offset + total] = b
                total += 1
            return total
        chunk = stream.read(length)
        if not chunk:
            return 0
        n = len(chunk)
        buf[offset : offset + n] = chunk
        return n

    def read_cid(self, input_stream: RandomAccessRead | BinaryIO) -> int:
        return self.to_cid(self.read_code(input_stream))

    # ---------- to_cid ----------

    def to_cid(self, code: int) -> int:
        """Convenience CID lookup. Returns 0 (the standard "no mapping"
        sentinel) when no mapping exists.

        See ``to_cid_with_length`` if the code's byte length is known —
        this overload may return false positives for ambiguous codes."""
        if not self.has_cid_mappings():
            return 0
        cid = 0
        length = self._min_cid_length
        while cid == 0 and length <= self._max_cid_length:
            cid = self.to_cid_with_length(code, length)
            length += 1
        return cid

    def to_cid_with_length(self, code: int, length: int) -> int:
        if (
            not self.has_cid_mappings()
            or length < self._min_cid_length
            or length > self._max_cid_length
        ):
            return 0
        cid_map = self._code_to_cid.get(length)
        if cid_map is not None:
            cid = cid_map.get(code)
            if cid is not None:
                return cid
        return self._to_cid_from_ranges_int(code, length)

    def to_cid_bytes(self, code: bytes | bytearray | memoryview) -> int:
        """Resolve a CID from the raw code byte sequence."""
        data = bytes(code)
        if (
            not self.has_cid_mappings()
            or len(data) < self._min_cid_length
            or len(data) > self._max_cid_length
        ):
            return 0
        cid_map = self._code_to_cid.get(len(data))
        if cid_map is not None:
            cid = cid_map.get(_to_int(data))
            if cid is not None:
                return cid
        return self._to_cid_from_ranges_bytes(data)

    def _to_cid_from_ranges_int(self, code: int, length: int) -> int:
        for rng in self._code_to_cid_ranges:
            ch = rng.map_int(code, length)
            if ch != -1:
                return ch
        return 0

    def _to_cid_from_ranges_bytes(self, code: bytes) -> int:
        for rng in self._code_to_cid_ranges:
            ch = rng.map_bytes(code)
            if ch != -1:
                return ch
        return 0

    # ---------- mutators (used by parser; public for tests) ----------

    def add_codespace_range(
        self,
        low_or_range: CodespaceRange | bytes | bytearray | memoryview,
        high: bytes | bytearray | memoryview | None = None,
    ) -> None:
        """Add a codespace range. Accepts either a constructed
        ``CodespaceRange`` (PDFBox parity) or low/high byte arrays."""
        if isinstance(low_or_range, CodespaceRange):
            rng = low_or_range
        else:
            if high is None:
                raise TypeError("add_codespace_range requires high bytes")
            rng = CodespaceRange(low_or_range, high)
        self._codespace_ranges.append(rng)
        cl = rng.get_code_length()
        if cl > self._max_code_length:
            self._max_code_length = cl
        if cl < self._min_code_length:
            self._min_code_length = cl

    def add_cid_mapping(
        self,
        code_or_int: bytes | bytearray | memoryview | int,
        cid: int,
    ) -> None:
        """Add a single code -> CID mapping. ``code`` is the raw input
        byte sequence (1-4 bytes)."""
        if isinstance(code_or_int, int):
            # Convenience overload — assume 2-byte CID code (the common case).
            data = _bytes_for_code(code_or_int, 2)
        else:
            data = bytes(code_or_int)
        cid_map = self._code_to_cid.get(len(data))
        if cid_map is None:
            cid_map = {}
            self._code_to_cid[len(data)] = cid_map
            if len(data) < self._min_cid_length:
                self._min_cid_length = len(data)
            if len(data) > self._max_cid_length:
                self._max_cid_length = len(data)
        cid_map[_to_int(data)] = cid

    def add_cid_range(self, frm: bytes, to: bytes, cid: int) -> None:
        """Add a CID range. Coalesces with the previous range if
        contiguous."""
        if len(frm) != len(to):
            raise ValueError("CID range start/end must have equal length")
        self._add_cid_range_int(_to_int(frm), _to_int(to), cid, len(frm))

    def _add_cid_range_int(
        self, frm: int, to: int, cid: int, length: int
    ) -> None:
        last = self._code_to_cid_ranges[-1] if self._code_to_cid_ranges else None
        if last is None or not last.extend(frm, to, cid, length):
            self._code_to_cid_ranges.append(_CIDRange(frm, to, cid, length))
            if length < self._min_cid_length:
                self._min_cid_length = length
            if length > self._max_cid_length:
                self._max_cid_length = length

    def add_unicode_mapping(self, code: int, unicode_str: str) -> None:
        """Set ``code -> unicode_str``. ``code`` is the integer form of
        the input code bytes; the byte length is inferred from
        the value (<=0xFF -> 1 byte, <=0xFFFF -> 2 bytes, ...).
        Use ``add_base_font_character`` if the byte length matters."""
        if code <= 0xFF:
            length = 1
        elif code <= 0xFFFF:
            length = 2
        elif code <= 0xFFFFFF:
            length = 3
        else:
            length = 4
        self.add_base_font_character(_bytes_for_code(code, length), unicode_str)

    def add_base_font_character(
        self, code_bytes: bytes | bytearray | memoryview, unicode_str: str
    ) -> None:
        """Equivalent to upstream ``addCharMapping(byte[], String)``."""
        codes = bytes(code_bytes)
        n = len(codes)
        if n == 1:
            self._char_to_unicode_one_byte[_to_int(codes)] = unicode_str
            self._unicode_to_byte_codes[unicode_str] = codes
        elif n == 2:
            self._char_to_unicode_two_bytes[_to_int(codes)] = unicode_str
            self._unicode_to_byte_codes[unicode_str] = codes
        elif n in (3, 4):
            self._char_to_unicode_more_bytes[_to_int(codes)] = unicode_str
            self._unicode_to_byte_codes[unicode_str] = codes
        else:
            _log.warning("Mappings with more than 4 bytes aren't supported yet")
            return
        if unicode_str == _SPACE:
            self._space_mapping = _to_int(codes)

    def get_codes_from_unicode(self, unicode_str: str) -> bytes | None:
        return self._unicode_to_byte_codes.get(unicode_str)

    def use_cmap(self, other: CMap) -> None:
        """Implementation of the ``usecmap`` operator — copy all mappings
        from ``other`` into ``self`` (without replacing existing CID
        mappings, but unioning per-length dicts)."""
        for r in other._codespace_ranges:
            self.add_codespace_range(r)
        self._char_to_unicode_one_byte.update(other._char_to_unicode_one_byte)
        self._char_to_unicode_two_bytes.update(other._char_to_unicode_two_bytes)
        self._char_to_unicode_more_bytes.update(other._char_to_unicode_more_bytes)
        for k, v in other._char_to_unicode_one_byte.items():
            self._unicode_to_byte_codes[v] = bytes([k & 0xFF])
        for k, v in other._char_to_unicode_two_bytes.items():
            self._unicode_to_byte_codes[v] = bytes([(k >> 8) & 0xFF, k & 0xFF])
        for k, v in other._char_to_unicode_more_bytes.items():
            length = 3 if k <= 0xFFFFFF else 4
            self._unicode_to_byte_codes[v] = _bytes_for_code(k, length)
        for length, mapping in other._code_to_cid.items():
            existing = self._code_to_cid.get(length)
            if existing is None:
                self._code_to_cid[length] = dict(mapping)
            else:
                existing.update(mapping)
        self._code_to_cid_ranges.extend(other._code_to_cid_ranges)
        if other._max_code_length > self._max_code_length:
            self._max_code_length = other._max_code_length
        if other._min_code_length < self._min_code_length:
            self._min_code_length = other._min_code_length
        if other._max_cid_length > self._max_cid_length:
            self._max_cid_length = other._max_cid_length
        if other._min_cid_length < self._min_cid_length:
            self._min_cid_length = other._min_cid_length

    # ---------- properties ----------

    def get_wmode(self) -> int:
        return self._wmode

    def set_wmode(self, new_wmode: int) -> None:
        self._wmode = new_wmode

    def get_name(self) -> str | None:
        return self._cmap_name

    def set_name(self, name: str) -> None:
        self._cmap_name = name

    def get_version(self) -> str | None:
        return self._cmap_version

    def set_version(self, version: str) -> None:
        self._cmap_version = version

    def get_type(self) -> int:
        return self._cmap_type

    def set_type(self, type_: int) -> None:
        self._cmap_type = type_

    def get_registry(self) -> str | None:
        return self._registry

    def set_registry(self, new_registry: str) -> None:
        self._registry = new_registry

    def get_ordering(self) -> str | None:
        return self._ordering

    def set_ordering(self, new_ordering: str) -> None:
        self._ordering = new_ordering

    def get_supplement(self) -> int:
        return self._supplement

    def set_supplement(self, new_supplement: int) -> None:
        self._supplement = new_supplement

    def get_space_mapping(self) -> int:
        return self._space_mapping

    def __str__(self) -> str:
        return self._cmap_name or ""
