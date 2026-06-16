from __future__ import annotations

import logging
from typing import BinaryIO, overload

from pypdfbox.io import RandomAccessRead

from .cid_range import CIDRange
from .codespace_range import CodespaceRange

_log = logging.getLogger(__name__)

_SPACE = " "

# Backwards-compatible alias for the package-private name used in earlier
# pypdfbox releases. Prefer ``CIDRange`` for new code.
_CIDRange = CIDRange


class CMapMappingError(KeyError):
    """Raised by :meth:`CMap.to_unicode` in ``strict=True`` mode when the
    requested code has no Unicode mapping defined."""


def _to_int(
    data: bytes | bytearray | memoryview,
    data_len: int | None = None,
    *,
    _offset: int = 0,
) -> int:
    """Big-endian byte sequence to int.

    ``_offset`` (keyword-only) lets callers slice without copying when
    walking a buffer — used by the bytes-form ``read_code``.
    """
    if data_len is None:
        data_len = len(data) - _offset
    code = 0
    for i in range(data_len):
        code = (code << 8) | (data[_offset + i] & 0xFF)
    return code


def _codespace_full_match(
    rng: CodespaceRange,
    data: bytes,
    offset: int,
    code_len: int,
) -> bool:
    """``rng.is_full_match`` against a slice of ``data`` without copying."""
    if rng.get_code_length() != code_len:
        return False
    start = rng._start  # noqa: SLF001 — intentional internal access for hot path
    end = rng._end  # noqa: SLF001
    for i in range(code_len):
        b = data[offset + i] & 0xFF
        if b < start[i] or b > end[i]:
            return False
    return True


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
        self._code_to_cid_ranges: list[CIDRange] = []

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

    def has_unicode_mapping(self) -> bool:
        """Singular alias for :meth:`has_unicode_mappings` — convenient when
        callers think of "does this CMap define any bfchar/bfrange data?"
        as a yes/no predicate. Equivalent to ``has_unicode_mappings()``."""
        return self.has_unicode_mappings()

    def has_cid_mapping(self) -> bool:
        """Singular alias for :meth:`has_cid_mappings`. Mirrors the
        ``has_unicode_mapping`` enrichment so callers can spell either
        predicate consistently. Equivalent to ``has_cid_mappings()``."""
        return self.has_cid_mappings()

    # ---------- to_unicode ----------

    def to_unicode(self, code: int, strict: bool = False) -> str | None:
        """Return the Unicode string for the given character code, or
        ``None`` if no mapping is defined.

        This convenience overload guesses the byte length from the value:
        codes < 256 are tried as 1-byte first, then 2-byte, etc.

        :param strict: when ``True`` raise :class:`CMapMappingError` instead
            of returning ``None`` if the code has no bfchar/bfrange mapping.
            Default ``False`` preserves the lenient upstream PDFBox
            behaviour (callers fall back to font-level encoding).
        """
        unicode_ = self.to_unicode_with_length(code, 1) if code < 256 else None
        if unicode_ is None:
            if code <= 0xFFFF:
                unicode_ = self.to_unicode_with_length(code, 2)
            elif code <= 0xFFFFFF:
                unicode_ = self.to_unicode_with_length(code, 3)
            else:
                unicode_ = self.to_unicode_with_length(code, 4)
        if unicode_ is None and strict:
            raise CMapMappingError(
                f"No Unicode mapping for code 0x{code:X} in CMap "
                f"{self._cmap_name!r}"
            )
        return unicode_

    def to_unicode_with_length(self, code: int, length: int) -> str | None:
        """Returns the Unicode string for ``code`` interpreted as ``length``
        input bytes, or ``None`` if no mapping is defined.

        Mirrors upstream ``CMap.toUnicode(int code, int length)`` —
        the unambiguous overload for callers that already know the
        origin byte length (1, 2, 3, or 4)."""
        if length == 1:
            return self._char_to_unicode_one_byte.get(code)
        if length == 2:
            return self._char_to_unicode_two_bytes.get(code)
        return self._char_to_unicode_more_bytes.get(code)

    # Internal alias retained for hot-path callers in this module.
    _to_unicode_with_len = to_unicode_with_length

    def to_unicode_bytes(self, code: bytes | bytearray | memoryview) -> str | None:
        """Lookup by raw input code bytes — the unambiguous form."""
        data = bytes(code)
        return self.to_unicode_with_length(_to_int(data), len(data))

    # ---------- read_code / read_cid ----------

    @overload
    def read_code(self, input_stream: RandomAccessRead | BinaryIO) -> int: ...

    @overload
    def read_code(
        self,
        input_stream: bytes | bytearray | memoryview,
        offset: int = 0,
    ) -> tuple[int, int]: ...

    def read_code(
        self,
        input_stream: RandomAccessRead | BinaryIO | bytes | bytearray | memoryview,
        offset: int = 0,
    ) -> int | tuple[int, int]:
        """Read a character code, dispatching on input type.

        * **Stream form** (``RandomAccessRead`` / ``BinaryIO``): mirrors
          upstream ``CMap.readCode(InputStream)`` — returns the matched
          code as an int. Reads ``min_code_length`` bytes, walks the
          codespace ranges, extending up to ``max_code_length`` on miss.
          On total failure, falls back to the first ``min_code_length``
          bytes (Adobe Reader behaviour).
        * **Bytes form** (``bytes`` / ``bytearray`` / ``memoryview``):
          pypdfbox enrichment — returns ``(code, code_byte_length)``
          starting at ``offset``. Useful for content-stream tokenisers
          that already have the bytes in hand and want both the int code
          AND the number of bytes consumed.

        Per ISO 32000-1 §9.7.6.2 — codespace ranges decide where one
        code ends and the next begins.

        :param input_stream: stream or bytes-like buffer to decode from.
        :param offset: starting byte offset (bytes form only).
        :raises TypeError: when ``offset`` is provided alongside a stream.
        """
        if isinstance(input_stream, (bytes, bytearray, memoryview)):
            return self._read_code_from_bytes(bytes(input_stream), offset)
        if offset:
            raise TypeError(
                "offset is only supported with bytes-like input"
            )
        return self._read_code_from_stream(input_stream)

    def _read_code_from_stream(
        self, input_stream: RandomAccessRead | BinaryIO
    ) -> int:
        max_len = self._max_code_length
        min_len = self._min_code_length
        if max_len <= 0:
            b = self._read_one(input_stream)
            return b if b >= 0 else 0
        bytes_buf = bytearray(max_len)

        # Read the initial minCodeLength bytes. Upstream ignores the actual
        # count returned by ``in.read(bytes, 0, minCodeLength)`` and runs the
        # codespace-matching loop over the (zero-padded) buffer regardless — so
        # a truncated tail shorter than ``minCodeLength`` still resolves to the
        # zero-extended code (e.g. a lone ``<41>`` under a ``<0000> <FFFF>``
        # codespace reads as ``0x4100``, consuming 1 byte). We mirror that
        # instead of short-circuiting (CMap.java readCode, verified against the
        # 3.0.7 bytecode where the read return value is discarded).
        self._read_some(input_stream, bytes_buf, 0, min_len)

        # Upstream marks the stream right after the initial minCodeLength bytes
        # (``in.mark(maxCodeLength)``) and, when no codespace range matches, calls
        # ``in.reset()`` before returning ``toInt(bytes, minCodeLength)`` — so the
        # speculatively-read extension bytes are pushed back and the *next* code
        # starts at offset ``minCodeLength``. We replicate that by counting the
        # extension bytes consumed past ``minCodeLength`` and rewinding them on a
        # total miss (CMap.java readCode mark/reset, verified against 3.0.7
        # bytecode).
        extra_read = 0
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
                extra_read += 1

        if extra_read:
            self._unread(input_stream, extra_read)

        if _log.isEnabledFor(logging.WARNING):
            sb = " ".join(f"0x{bytes_buf[i] & 0xFF:02X}" for i in range(max_len))
            _log.warning(
                "Invalid character code sequence %s in CMap %s",
                sb,
                self._cmap_name,
            )
        return _to_int(bytes_buf, min_len)

    def _read_code_from_bytes(
        self, data: bytes, offset: int
    ) -> tuple[int, int]:
        """Bytes-form ``read_code`` — returns ``(code, code_byte_length)``.

        ``code_byte_length`` is the number of input bytes consumed, so
        callers can advance their cursor as ``offset += length``.
        """
        if offset < 0 or offset > len(data):
            raise ValueError(
                f"offset {offset} out of range for buffer of length "
                f"{len(data)}"
            )
        max_len = self._max_code_length
        min_len = self._min_code_length
        available = len(data) - offset

        # No codespace ranges defined — fall back to the first available byte.
        if max_len <= 0:
            if available <= 0:
                return 0, 0
            return data[offset] & 0xFF, 1

        if available <= 0:
            return 0, 0

        # Truncated tail — return whatever we have so the caller can stop.
        if available < min_len:
            return _to_int(data, available, _offset=offset), available

        for byte_count in range(min_len, min(max_len, available) + 1):
            for r in self._codespace_ranges:
                if _codespace_full_match(r, data, offset, byte_count):
                    return _to_int(data, byte_count, _offset=offset), byte_count

        if _log.isEnabledFor(logging.WARNING):
            end = min(offset + max_len, len(data))
            sb = " ".join(
                f"0x{data[i] & 0xFF:02X}" for i in range(offset, end)
            )
            _log.warning(
                "Invalid character code sequence %s in CMap %s",
                sb,
                self._cmap_name,
            )
        return _to_int(data, min_len, _offset=offset), min_len

    def code_length_at(self, byte_value: int) -> int | None:
        """Return the expected byte length of a code beginning with
        ``byte_value`` according to the codespace tree, or ``None`` if no
        codespace range starts with that byte.

        For most CJK CMaps a leading byte uniquely determines whether the
        whole code is 1 or 2 bytes (e.g. Adobe-Japan1: 0x00–0x7F → 1 byte,
        0x81–0x9F / 0xE0–0xFC → 2 bytes). When multiple codespace ranges
        are compatible with the same leading byte, the **shortest** match
        wins — that is the byte length the parser would commit to first
        per ISO 32000-1 §9.7.6.2.
        """
        if not self._codespace_ranges:
            return None
        b = byte_value & 0xFF
        best: int | None = None
        for r in self._codespace_ranges:
            start_byte = r._start[0]
            end_byte = r._end[0]
            if start_byte <= b <= end_byte:
                cl = r.get_code_length()
                if best is None or cl < best:
                    best = cl
        return best

    @staticmethod
    def _unread(stream: RandomAccessRead | BinaryIO, n: int) -> None:
        """Push back ``n`` previously-read bytes, mirroring upstream's
        ``in.reset()`` after ``in.mark(maxCodeLength)`` in ``readCode``.

        For a ``RandomAccessRead`` we use ``rewind``; for a seekable
        ``BinaryIO`` we ``seek`` backwards relative to the current position.
        A non-seekable stream silently keeps the bytes consumed — matching
        upstream's behaviour when ``markSupported()`` is ``False`` (it logs
        "mark() and reset() not supported" and the bytes stay skipped).
        """
        if n <= 0:
            return
        if isinstance(stream, RandomAccessRead):
            stream.rewind(n)
            return
        seekable = getattr(stream, "seekable", None)
        if seekable is not None and seekable():
            stream.seek(-n, 1)

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

    def to_cid_from_ranges(
        self,
        code: bytes | bytearray | memoryview | int,
        length: int | None = None,
    ) -> int:
        """Look up a CID solely against the registered CID ranges, ignoring
        the per-length ``codeToCid`` direct-mapping dicts.

        Direct port of the two private upstream overloads
        ``toCIDFromRanges(int, int)`` and ``toCIDFromRanges(byte[])``
        (CMap.java lines 310 and 330). pypdfbox makes the entry public so
        differential tests can probe range lookup in isolation; production
        callers should prefer :meth:`to_cid` or :meth:`to_cid_bytes` which
        also consult the direct mappings.

        Returns ``0`` (the standard "no mapping" sentinel) when no range
        covers the code.
        """
        if isinstance(code, int):
            if length is None:
                raise TypeError(
                    "to_cid_from_ranges(code, length) requires length when "
                    "code is an int"
                )
            return self._to_cid_from_ranges_int(code, length)
        return self._to_cid_from_ranges_bytes(bytes(code))

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
            self._code_to_cid_ranges.append(CIDRange(frm, to, cid, length))
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

    def add_char_mapping(
        self, codes: bytes | bytearray | memoryview, unicode_str: str
    ) -> None:
        """Direct port of upstream ``CMap.addCharMapping(byte[], String)``
        (CMap.java line 349). Adds a character-code-to-Unicode mapping
        keyed by the input byte length (1, 2, 3, or 4).

        This is the canonical name; :meth:`add_base_font_character` is
        retained as a synonym for callers that prefer the descriptive
        spelling derived from the ``beginbfchar`` PostScript operator.
        """
        self.add_base_font_character(codes, unicode_str)

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

    # Strict camel-to-snake mapping of upstream ``getWMode``/``setWMode``
    # (CMap.java lines 502, 512). PDFBox treats ``WMode`` as a single token.
    # ``get_wmode``/``set_wmode`` above are retained as ergonomic synonyms
    # used throughout the existing pypdfbox call sites; both spellings are
    # kept in lockstep so callers can pick whichever reads better.
    def get_w_mode(self) -> int:
        return self._wmode

    def set_w_mode(self, new_w_mode: int) -> None:
        self._wmode = new_w_mode

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

    # ---------- writing-mode predicates ----------

    def is_horizontal(self) -> bool:
        """``True`` when the CMap declares horizontal writing mode (WMode 0).

        pypdfbox enrichment — upstream exposes only ``getWMode()`` and
        leaves callers to compare against ``0``/``1`` themselves. The
        predicate makes call sites read more naturally (``if cmap.is_vertical()``).
        Per ISO 32000-1 §9.7.5.4 a CMap's ``WMode`` is either ``0`` (horizontal)
        or ``1`` (vertical); any other value (e.g. uninitialized custom CMaps)
        is treated as horizontal here, which mirrors the upstream default.
        """
        return self._wmode != 1

    def is_vertical(self) -> bool:
        """``True`` when the CMap declares vertical writing mode (WMode 1).

        Inverse of :meth:`is_horizontal`. pypdfbox enrichment — see that
        method for the rationale.
        """
        return self._wmode == 1

    # ---------- code / cid length accessors ----------

    def get_min_code_length(self) -> int:
        """Smallest code byte length covered by any registered codespace
        range. Defaults to ``4`` on an empty CMap (matches upstream's
        ``minCodeLength`` initial value, used as the lower bound of the
        ``readCode`` walk in ISO 32000-1 §9.7.6.2).
        """
        return self._min_code_length

    def get_max_code_length(self) -> int:
        """Largest code byte length covered by any registered codespace
        range. Defaults to ``0`` on an empty CMap (matches upstream's
        ``maxCodeLength`` initial value).
        """
        return self._max_code_length

    def get_min_cid_length(self) -> int:
        """Smallest input byte length seen in any CID mapping. Defaults to
        ``4`` on an empty CMap (matches upstream's ``minCidLength`` initial
        value).
        """
        return self._min_cid_length

    def get_max_cid_length(self) -> int:
        """Largest input byte length seen in any CID mapping. Defaults to
        ``0`` on an empty CMap (matches upstream's ``maxCidLength`` initial
        value).
        """
        return self._max_cid_length

    def get_codespace_ranges(self) -> list[CodespaceRange]:
        """Snapshot copy of the registered codespace ranges.

        pypdfbox enrichment — upstream keeps ``codespaceRanges`` package-private
        and only exposes it via ``readCode``. Returning a fresh list keeps
        callers from mutating the internal state while letting tests / tools
        inspect the codespace structure directly. Order matches insertion
        order (which is the order the parser saw ``begincodespacerange``
        entries).
        """
        return list(self._codespace_ranges)

    # ---------- CIDSystemInfo registry / typed accessors ----------

    def get_cid_system_info(self) -> dict[str, object] | None:
        """Return the parsed ``/CIDSystemInfo`` triple as a typed dict.

        pypdfbox enrichment — upstream stores the three values as bare
        strings on ``CMap`` and never groups them. The typed dict makes
        it ergonomic to round-trip a CMap-derived ``CIDSystemInfo`` into
        a font's ``/CIDSystemInfo`` dictionary (see
        :class:`pypdfbox.pdmodel.font.PDCIDSystemInfo`).

        Returns ``None`` when neither ``Registry`` nor ``Ordering`` was
        recorded — predefined CMaps always populate both.
        """
        if self._registry is None and self._ordering is None:
            return None
        return {
            "Registry": self._registry,
            "Ordering": self._ordering,
            "Supplement": self._supplement,
        }

    def get_combined_name(self) -> str | None:
        """``Registry-Ordering-Supplement`` triple as a single string.

        Mirrors the convention used throughout PDFBox font code (e.g.
        ``Adobe-Japan1-6``) for matching CMap CIDSystemInfo against a
        font's CIDSystemInfo. Returns ``None`` if either ``Registry`` or
        ``Ordering`` is missing.
        """
        if not self._registry or not self._ordering:
            return None
        return f"{self._registry}-{self._ordering}-{self._supplement}"

    @staticmethod
    def to_int(
        data: bytes | bytearray | memoryview, data_len: int | None = None
    ) -> int:
        """Big-endian byte sequence to int.

        Direct port of upstream ``CMap.toInt(byte[])`` and the private
        two-arg overload ``toInt(byte[], int)`` (CMap.java lines 214 / 222).
        pypdfbox exposes both via a single static method with an optional
        ``data_len`` argument — when omitted the full buffer is consumed,
        matching the package-private upstream entry point.
        """
        return _to_int(data, data_len)

    def to_string(self) -> str:
        """Return the CMap name, or an empty string if unset.

        Direct port of upstream ``CMap.toString()`` (CMap.java line 648).
        Equivalent to ``str(cmap)`` — kept as a separate method so the Java
        idiom ``cmap.toString()`` translates one-to-one into ``cmap.to_string()``.
        """
        return self._cmap_name or ""

    def __str__(self) -> str:
        return self._cmap_name or ""
