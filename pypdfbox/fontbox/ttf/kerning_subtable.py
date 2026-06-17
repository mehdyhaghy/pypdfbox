from __future__ import annotations

import bisect
import struct
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .true_type_font import TrueTypeFont
    from .ttf_data_stream import TTFDataStream


class KerningSubtable:
    """A single subtable of a TrueType ``kern`` table.

    Mirrors ``org.apache.fontbox.ttf.KerningSubtable`` at the public-method
    level. Two construction paths are supported:

    * Wrapping a fontTools ``KernTable_format_0`` instance (default
      :meth:`__init__`). fontTools already understands both OpenType and
      Apple layouts.
    * Direct on-disk parsing via :meth:`from_bytes`, for the upstream
      OpenType formats PDFBox handles natively — Format 0 (sorted pair
      list) and Format 2 (class-based pair lookup, used by very large
      kerning tables to keep size down).

    Format 1 / Apple extended-format subtables are exposed but report
    ``get_kerning`` of 0 for any pair, matching upstream's "unsupported
    subtable" behaviour where ``pairs`` stays ``None`` and the warning is
    logged.
    """

    # Coverage bit masks / shifts — kept identical to upstream so callers
    # that go looking for the constants find them in the expected place.
    COVERAGE_HORIZONTAL: int = 0x0001
    COVERAGE_MINIMUMS: int = 0x0002
    COVERAGE_CROSS_STREAM: int = 0x0004
    COVERAGE_FORMAT: int = 0xFF00

    COVERAGE_HORIZONTAL_SHIFT: int = 0
    COVERAGE_MINIMUMS_SHIFT: int = 1
    COVERAGE_CROSS_STREAM_SHIFT: int = 2
    COVERAGE_FORMAT_SHIFT: int = 8

    def __init__(
        self,
        ft_subtable: Any = None,
        ttf: TrueTypeFont | None = None,
    ) -> None:
        # ft_subtable is a fontTools KernTable_format_0 (or
        # KernTable_format_unkown) instance. We pull only what's needed
        # to evaluate coverage flags and look up a pair value.
        self._ft = ft_subtable
        self._ttf = ttf

        # Format-2 class-based lookup state (only populated by
        # :meth:`from_bytes` when format == 2).
        self._gid_to_left_class: dict[int, int] | None = None
        self._gid_to_right_class: dict[int, int] | None = None
        self._class_kerning: list[int] | None = None
        self._class_row_width: int = 0

        # Integer-keyed gid -> gid -> value lookup populated by
        # :meth:`from_bytes` for format 0. Distinct from ``_pairs`` (which
        # holds glyph-name keys when wrapping fontTools output).
        self._gid_pairs: dict[tuple[int, int], int] | None = None

        if ft_subtable is None:
            # Bare-bones constructor used by :meth:`from_bytes` — caller
            # populates the fields directly.
            self._coverage = 0
            self._horizontal = False
            self._minimums = False
            self._cross_stream = False
            self._format = 0
            self._pairs = None
            return

        # In fontTools, OpenType non-Apple ``coverage`` is the low byte
        # of the upstream 16-bit coverage word and ``format`` is the high
        # byte. Re-encode them into the upstream layout so the bit-mask
        # constants above are still meaningful for callers that read
        # ``self._coverage`` directly.
        ft_coverage = int(getattr(ft_subtable, "coverage", 0))
        ft_format = int(getattr(ft_subtable, "format", 0))
        if getattr(ft_subtable, "apple", False):
            # Apple uses an 8-bit coverage byte where bit 7 is "horizontal"
            # (inverted relative to OpenType) and bits 13-15 carry the
            # cross-stream / variation flags. We do not currently support
            # Apple-style kern subtables for ``getKerning`` lookup
            # anyway — leave coverage as exposed by fontTools, and the
            # horizontal/minimums/cross-stream booleans below stay False.
            self._coverage = ft_coverage
            self._horizontal = False
            self._minimums = False
            self._cross_stream = False
        else:
            self._coverage = ((ft_format & 0xFF) << 8) | (ft_coverage & 0xFF)
            self._horizontal = (
                self._coverage & self.COVERAGE_HORIZONTAL
            ) >> self.COVERAGE_HORIZONTAL_SHIFT != 0
            self._minimums = (
                self._coverage & self.COVERAGE_MINIMUMS
            ) >> self.COVERAGE_MINIMUMS_SHIFT != 0
            self._cross_stream = (
                self._coverage & self.COVERAGE_CROSS_STREAM
            ) >> self.COVERAGE_CROSS_STREAM_SHIFT != 0

        self._format = ft_format
        # ``pairs`` mirrors upstream: only populated for format 0; any
        # other format leaves it None, and getKerning then returns 0.
        kern_table = getattr(ft_subtable, "kernTable", None)
        if self._format == 0 and isinstance(kern_table, dict):
            self._pairs = kern_table
        else:
            self._pairs = None

    # ---------- direct binary parsing (Format 0 + Format 2) ----------

    def read(self, data: TTFDataStream, version: int) -> None:
        """Read this subtable from a :class:`TTFDataStream` at the current
        position, mirroring upstream ``KerningSubtable#read(TTFDataStream, int)``.

        ``version`` is the parent ``kern`` table version (0 = OpenType,
        1 = Apple). Other values raise :class:`ValueError` (upstream throws
        ``IllegalStateException``).
        """
        if version == 0:
            self.read_subtable0(data)
        elif version == 1:
            self.read_subtable1(data)
        else:
            raise ValueError(f"unknown kern table version {version}")

    def read_subtable0(self, data: TTFDataStream) -> None:
        """Mirror of upstream ``readSubtable0(TTFDataStream)`` — OpenType
        layout. Public-by-snake-case for parity but considered package-
        private; prefer :meth:`read` as the entry point."""
        self._read_subtable_0(data)

    def read_subtable1(self, data: TTFDataStream) -> None:
        """Mirror of upstream ``readSubtable1(TTFDataStream)`` — Apple
        ``kern`` v1 layout. Upstream logs "not yet supported" and leaves
        ``pairs`` unset; we do the same."""
        self._read_subtable_1(data)

    def read_subtable0_format0(self, data: TTFDataStream) -> None:
        """Mirror of upstream ``readSubtable0Format0(TTFDataStream)`` — body
        reader for the sorted pair list (Format 0). Reads the binary-search
        header (nPairs, searchRange, entrySelector, rangeShift) then nPairs
        entries of (left uint16, right uint16, value int16)."""
        self._read_subtable_0_format_0_stream(data)

    def read_subtable0_format2(self, data: TTFDataStream) -> None:
        """Mirror of upstream ``readSubtable0Format2(TTFDataStream)`` — body
        reader for the class-based subtable (Format 2). Upstream simply
        logs "not yet supported" inside this helper; the actual decoder is
        the byte-buffer based :meth:`_read_format_2`. We dispatch to that
        when called with a stream by reading the remaining bytes first."""
        # Upstream's helper is a no-op log; we keep behaviour-parity by
        # reading nothing (caller has already consumed the header). The
        # buffer-driven Format 2 path is reached via the ``length``-aware
        # dispatch in :meth:`_read_subtable_0`.
        del data

    def _read_subtable_0(self, data: TTFDataStream) -> None:
        """Upstream ``readSubtable0`` — OpenType layout. Reads the 6-byte
        OpenType subtable header (version, length, coverage) then dispatches
        on the format byte (high byte of coverage). Format 0 → sorted pair
        list (binary search); Format 2 → class-based; anything else logs
        and leaves ``pairs`` unset so :meth:`get_kerning` returns 0."""
        sub_version = data.read_unsigned_short()
        if sub_version != 0:
            # Upstream "Unsupported kerning sub-table version" log; bail out.
            return
        length = data.read_unsigned_short()
        if length < 6:
            # Upstream "Kerning sub-table too short" log; bail out.
            return
        coverage = data.read_unsigned_short()
        self._coverage = coverage
        # Use the upstream-style bit-field helpers so behaviour matches
        # exactly even on edge-case coverage values.
        self._horizontal = self.is_bits_set(
            coverage, self.COVERAGE_HORIZONTAL, self.COVERAGE_HORIZONTAL_SHIFT
        )
        self._minimums = self.is_bits_set(
            coverage, self.COVERAGE_MINIMUMS, self.COVERAGE_MINIMUMS_SHIFT
        )
        self._cross_stream = self.is_bits_set(
            coverage, self.COVERAGE_CROSS_STREAM, self.COVERAGE_CROSS_STREAM_SHIFT
        )
        self._format = self.get_bits(
            coverage, self.COVERAGE_FORMAT, self.COVERAGE_FORMAT_SHIFT
        )
        if self._format == 0:
            self._read_subtable_0_format_0_stream(data)
        elif self._format == 2:
            # Read remaining ``length - 6`` bytes and parse via the in-memory
            # Format 2 path; class-based bodies use absolute offsets relative
            # to the subtable header, which the buffer-based parser already
            # handles correctly.
            body = data.read_bytes(max(0, length - 6))
            self._read_format_2(body)
        # other formats: leave pairs unset → 0 lookup (upstream parity)

    def _read_subtable_0_format_0_stream(self, data: TTFDataStream) -> None:
        """Upstream ``readSubtable0Format0`` body reader. nPairs (uint16),
        searchRange (uint16), entrySelector (uint16), rangeShift (uint16),
        then nPairs * (left, right, value) where value is signed int16."""
        n_pairs = data.read_unsigned_short()
        # Three more uint16s are part of the binary-search header upstream
        # uses but we don't need them for our dict / sorted-list lookup.
        data.read_unsigned_short()  # searchRange
        data.read_unsigned_short()  # entrySelector
        data.read_unsigned_short()  # rangeShift
        pairs: dict[tuple[int, int], int] = {}
        for _ in range(n_pairs):
            left = data.read_unsigned_short()
            right = data.read_unsigned_short()
            value = data.read_signed_short()
            pairs[(left, right)] = value
        self._gid_pairs = pairs

    def _read_subtable_1(self, data: TTFDataStream) -> None:  # noqa: ARG002
        """Upstream ``readSubtable1`` — Apple state-machine layout. Logged as
        "not yet supported" upstream; leave ``pairs`` unset → 0 lookup."""
        return

    @staticmethod
    def is_bits_set(bits: int, mask: int, shift: int) -> bool:
        """Mirror of upstream ``isBitsSet(int bits, int mask, int shift)``.

        True when the masked & shifted value is non-zero. Used by the
        coverage-flag decoder when reading a Format 0 subtable header."""
        return KerningSubtable.get_bits(bits, mask, shift) != 0

    @staticmethod
    def get_bits(bits: int, mask: int, shift: int) -> int:
        """Mirror of upstream ``getBits(int bits, int mask, int shift)``.

        Extract a bit field from ``bits`` selected by ``mask`` and shift
        it down by ``shift`` to its low-order representation."""
        return (bits & mask) >> shift

    @classmethod
    def from_bytes(
        cls,
        data: bytes,
        version: int = 0,
    ) -> KerningSubtable:
        """Parse a single ``kern`` subtable from raw bytes.

        ``data`` must include the subtable header (version, length, coverage)
        followed by the format-specific body. ``version`` selects between
        the OpenType layout (``0``) and the Apple ``kern`` layout (``1``);
        the OpenType layout is what PDFBox parses natively.

        Supports Format 0 (sorted pair list) and Format 2 (class-based).
        Other formats are accepted but produce a subtable that returns 0
        for any pair lookup, matching upstream's "unsupported subtable"
        behaviour.
        """
        sub = cls()
        if version == 0:
            # OpenType subtable header: version (uint16), length (uint16),
            # coverage (uint16). Coverage low byte = flags, high byte = format.
            if len(data) < 6:
                raise ValueError("kern subtable too short for OpenType header")
            sub_version, _length, coverage = struct.unpack_from(">HHH", data, 0)
            del sub_version
            body = data[6:]
        else:
            # Apple ``kern`` v1 subtable header: length (uint32),
            # coverage (uint16), tupleIndex (uint16). We only really need
            # coverage; format is bits 0-7 of the low byte and direction
            # / cross-stream / variation in the high byte.
            if len(data) < 8:
                raise ValueError("kern subtable too short for Apple header")
            _length, coverage, _tuple = struct.unpack_from(">IHH", data, 0)
            body = data[8:]

        sub._coverage = coverage
        if version == 0:
            sub._format = (coverage & cls.COVERAGE_FORMAT) >> cls.COVERAGE_FORMAT_SHIFT
            sub._horizontal = bool(coverage & cls.COVERAGE_HORIZONTAL)
            sub._minimums = bool(coverage & cls.COVERAGE_MINIMUMS)
            sub._cross_stream = bool(coverage & cls.COVERAGE_CROSS_STREAM)
        else:
            # Apple coverage layout differs (vertical bit set means vertical,
            # so horizontal = NOT bit 15). We don't need full parity — leave
            # the booleans False so unsupported-subtable lookup applies.
            sub._format = coverage & 0xFF
            sub._horizontal = False
            sub._minimums = False
            sub._cross_stream = False

        if sub._format == 0:
            sub._read_format_0(body)
        elif sub._format == 2:
            sub._read_format_2(body)
        # Other formats: leave _pairs / class tables unset → 0 lookup.
        return sub

    def _read_format_0(self, body: bytes) -> None:
        """Parse a Format 0 (sorted pair list) subtable body.

        Layout: nPairs (uint16), searchRange (uint16), entrySelector (uint16),
        rangeShift (uint16), then nPairs * (left uint16, right uint16,
        value int16) entries sorted by (left, right).
        """
        if len(body) < 8:
            raise ValueError("kern format-0 body too short")
        n_pairs, _search, _entry_sel, _range_shift = struct.unpack_from(
            ">HHHH", body, 0
        )
        pairs: dict[tuple[int, int], int] = {}
        offset = 8
        for _ in range(n_pairs):
            if offset + 6 > len(body):
                break
            left, right, value = struct.unpack_from(">HHh", body, offset)
            pairs[(left, right)] = value
            offset += 6
        self._gid_pairs = pairs

    def _read_format_2(self, body: bytes) -> None:
        """Parse a Format 2 (class-based) subtable body.

        Layout: rowWidth (uint16), leftClassTableOffset (uint16),
        rightClassTableOffset (uint16), arrayOffset (uint16). Offsets are
        measured from the start of the subtable header (i.e. before the
        6-byte OpenType header), so we add 6 to each.

        Each class table starts with firstGlyph (uint16), nGlyphs (uint16)
        followed by nGlyphs uint16 class values. The kerning array is a
        block of int16 values; the kerning value for (left_gid, right_gid)
        is ``array[leftClass + rightClass]`` (offsets in bytes within the
        subtable, so leftClass already counts in row-width units).
        """
        if len(body) < 8:
            raise ValueError("kern format-2 body too short")
        row_width, left_off, right_off, array_off = struct.unpack_from(
            ">HHHH", body, 0
        )
        # Offsets are from the start of the subtable header (before the
        # 6-byte OpenType header). Re-base them onto ``body``.
        header_size = 6
        left_base = left_off - header_size
        right_base = right_off - header_size
        array_base = array_off - header_size

        gid_to_left = self._read_class_table(body, left_base)
        gid_to_right = self._read_class_table(body, right_base)
        # The kerning array runs from array_base to end of body. Decode as
        # a flat int16 list — index lookup is (leftClass + rightClass) bytes.
        array_bytes = body[array_base:]
        n_values = len(array_bytes) // 2
        values = list(struct.unpack(">" + "h" * n_values, array_bytes[: n_values * 2]))

        self._gid_to_left_class = gid_to_left
        self._gid_to_right_class = gid_to_right
        self._class_kerning = values
        self._class_row_width = row_width

    @staticmethod
    def _read_class_table(body: bytes, base: int) -> dict[int, int]:
        """Decode one class-mapping subtable returning gid → class value
        (in bytes — Format 2 stores class values as byte offsets, so the
        caller indexes the kerning array directly without further scaling)."""
        if base < 0 or base + 4 > len(body):
            return {}
        first_glyph, n_glyphs = struct.unpack_from(">HH", body, base)
        result: dict[int, int] = {}
        offset = base + 4
        for i in range(n_glyphs):
            if offset + 2 > len(body):
                break
            (cls_value,) = struct.unpack_from(">H", body, offset)
            result[first_glyph + i] = cls_value
            offset += 2
        return result

    # ---------- coverage accessors ----------

    def is_horizontal_kerning(self, cross: bool = False) -> bool:
        """True if the subtable describes inline-progression kerning for
        horizontal writing modes (i.e. ``getKerning`` returns useful pair
        adjustments for horizontal text layout).

        With ``cross=False`` (default), require the cross-stream flag to
        be unset; with ``cross=True``, require it to be set. In either
        case minimum-value subtables are excluded.
        """
        if not self._horizontal:
            return False
        if self._minimums:
            return False
        if cross:
            return self._cross_stream
        return not self._cross_stream

    def is_horizontal(self) -> bool:
        """Raw value of the coverage ``horizontal`` bit."""
        return self._horizontal

    def is_minimum(self) -> bool:
        """Raw value of the coverage ``minimums`` bit."""
        return self._minimums

    def is_cross_stream(self) -> bool:
        """Raw value of the coverage ``cross-stream`` bit."""
        return self._cross_stream

    def get_format(self) -> int:
        """Subtable format (0 / 1 / 2 / 3). Formats 0 and 2 carry pair data
        when parsed via :meth:`from_bytes`; format 1 / 3 / Apple extended
        formats are exposed but report zero adjustments."""
        return self._format

    def get_coverage(self) -> int:
        """Reconstructed 16-bit upstream coverage word (format in high byte,
        flags in low byte)."""
        return self._coverage

    # ---------- pair lookup ----------

    def get_kerning(self, *args: Any) -> Any:
        """Look up a kerning adjustment.

        Two call shapes mirror upstream Java overloads:

        * ``get_kerning(left_gid, right_gid)`` -> int. Returns the kerning
          adjustment for that ordered pair, in font design units. Returns
          0 when the pair is absent or the subtable format is unsupported.
        * ``get_kerning(glyphs)`` -> list[int]. Given a sequence of glyph
          IDs, returns a list of adjustments where the Nth entry is the
          adjustment between glyph N and the next non-negative glyph in
          the sequence; matches upstream ``getKerning(int[])``.
        """
        if len(args) == 1:
            return self._get_kerning_seq(args[0])
        if len(args) == 2:
            left, right = args
            return self._get_kerning_pair(int(left), int(right))
        raise TypeError(
            f"get_kerning() takes 1 or 2 positional args, got {len(args)}"
        )

    def _get_kerning_pair(self, left: int, right: int) -> int:
        if left < 0 or right < 0:
            return 0
        # Format-2 class-based lookup.
        if self._class_kerning is not None and self._gid_to_left_class is not None:
            assert self._gid_to_right_class is not None
            left_cls = self._gid_to_left_class.get(left, 0)
            right_cls = self._gid_to_right_class.get(right, 0)
            # Class values are byte offsets — divide by 2 since we store the
            # array as int16 entries.
            idx = (left_cls + right_cls) // 2
            if 0 <= idx < len(self._class_kerning):
                return int(self._class_kerning[idx])
            return 0
        # Format-0 binary-parsed (gid-keyed) lookup. Mirrors upstream's
        # ``Arrays.binarySearch`` over the sorted (left, right, value) list:
        # we keep the dict as the primary store (O(1) lookup) but also
        # expose a ``_sorted_pairs`` view for callers that want
        # binary-search semantics — see :meth:`binary_search_pair`.
        if self._gid_pairs is not None:
            return int(self._gid_pairs.get((left, right), 0))
        # Format-0 fontTools-wrapped (glyph-name keyed) lookup.
        if self._pairs is None:
            return 0
        # fontTools stores keys as (glyph_name, glyph_name) tuples — we
        # need to project the GIDs back through the glyph order to look
        # them up.
        if self._ttf is None:
            return 0
        glyph_order = self._ttf._tt.getGlyphOrder()  # noqa: SLF001
        if left >= len(glyph_order) or right >= len(glyph_order):
            return 0
        key = (glyph_order[left], glyph_order[right])
        value = self._pairs.get(key)
        if value is None:
            return 0
        return int(value)

    def binary_search_pair(self, left: int, right: int) -> int:
        """Upstream-style binary search over a sorted (left, right) pair
        list — returns the kerning value or 0 if the pair is absent.

        Provided as a parity helper that mirrors the
        ``Arrays.binarySearch(pairs, key, this)`` call in upstream's
        ``PairData0Format0#getKerning``. The default :meth:`get_kerning`
        path uses an O(1) dict instead; both must produce the same result.
        """
        if self._gid_pairs is None or left < 0 or right < 0:
            return 0
        # Build / cache the sorted-pair view lazily.
        sorted_pairs = getattr(self, "_sorted_pairs_cache", None)
        if sorted_pairs is None:
            sorted_pairs = sorted(self._gid_pairs.items(), key=lambda kv: kv[0])
            self._sorted_pairs_cache = sorted_pairs
        keys = [kv[0] for kv in sorted_pairs]
        idx = bisect.bisect_left(keys, (left, right))
        if 0 <= idx < len(keys) and keys[idx] == (left, right):
            return int(sorted_pairs[idx][1])
        return 0

    def _get_kerning_seq(
        self, glyphs: list[int] | tuple[int, ...]
    ) -> list[int] | None:
        result: list[int] = []
        if (
            self._pairs is None
            and self._gid_pairs is None
            and self._class_kerning is None
        ):
            # Upstream ``getKerning(int[])`` returns ``null`` (not a zero-filled
            # array) when ``pairs == null`` — the "unsupported kerning subtable"
            # case. Mirror that by returning None rather than [0] * len(glyphs).
            return None
        ng = len(glyphs)
        for i in range(ng):
            left = int(glyphs[i])
            right = -1
            for k in range(i + 1, ng):
                g = int(glyphs[k])
                if g >= 0:
                    right = g
                    break
            result.append(self._get_kerning_pair(left, right))
        return result


__all__ = ["KerningSubtable"]
