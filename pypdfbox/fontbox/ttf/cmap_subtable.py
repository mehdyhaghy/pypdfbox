from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .cmap_lookup import CmapLookup

if TYPE_CHECKING:
    from .cmap_table import CmapTable
    from .ttf_data_stream import TTFDataStream

_LOG = logging.getLogger(__name__)

_LEAD_OFFSET: int = 0xD800 - (0x10000 >> 10)
_SURROGATE_OFFSET: int = 0x10000 - (0xD800 << 10) - 0xDC00


class CmapSubtable(CmapLookup):
    """A single cmap subtable.

    Mirrors ``org.apache.fontbox.ttf.CmapSubtable``.

    Implements all OpenType ``cmap`` subtable formats:

    * Format 0  — byte encoding table
    * Format 2  — high-byte mapping (DBCS / legacy CJK)
    * Format 4  — segment mapping to delta values (BMP)
    * Format 6  — trimmed table mapping
    * Format 8  — mixed 16/32-bit coverage (legacy)
    * Format 10 — trimmed array
    * Format 12 — segmented coverage (full Unicode)
    * Format 13 — many-to-one mappings (Last Resort font)
    * Format 14 — Unicode Variation Sequences (UVS) — parsed but not
      surfaced through ``get_glyph_id`` (UVS lookup uses a separate
      ``get_glyph_id_uvs`` helper because a base codepoint plus a variation
      selector together resolve to a glyph).
    """

    def __init__(self) -> None:
        self._platform_id: int = 0
        self._platform_encoding_id: int = 0
        self._sub_table_offset: int = 0
        self._glyph_id_to_character_code: list[int] | None = None
        self._glyph_id_to_character_code_multiple: dict[int, list[int]] = {}
        self._character_code_to_glyph_id: dict[int, int] = {}
        # Format 14 (UVS) state — keyed by (base_codepoint, variation_selector)
        # → glyph_id. ``_default_uvs`` lists (selector, start, end) ranges for
        # which the variation defaults to the underlying base glyph.
        self._uvs_mapping: dict[tuple[int, int], int] = {}
        self._default_uvs: list[tuple[int, int, int]] = []

    def init_data(self, data: TTFDataStream) -> None:
        self._platform_id = data.read_unsigned_short()
        self._platform_encoding_id = data.read_unsigned_short()
        self._sub_table_offset = data.read_unsigned_int()

    def init_subtable(self, cmap: CmapTable, num_glyphs: int, data: TTFDataStream) -> None:
        data.seek(cmap.get_offset() + self._sub_table_offset)
        subtable_format = data.read_unsigned_short()
        # Header bytes after the format word vary across formats:
        # * formats < 8           : length(uint16), version(uint16)
        # * format 14             : length(uint32) — and numVarSelectorRecords
        #                           (uint32) is consumed by the format-14 reader
        #                           itself (it needs the value).
        # * other formats >= 8    : reserved(uint16), length(uint32), language(uint32)
        if subtable_format < 8:
            length = data.read_unsigned_short()  # noqa: F841
            version = data.read_unsigned_short()  # noqa: F841
        elif subtable_format == 14:
            length = data.read_unsigned_int()  # noqa: F841
        else:
            data.read_unsigned_short()
            length = data.read_unsigned_int()  # noqa: F841
            version = data.read_unsigned_int()  # noqa: F841

        if subtable_format == 0:
            self._process_subtype_0(data)
        elif subtable_format == 2:
            self._process_subtype_2(data, num_glyphs)
        elif subtable_format == 4:
            self._process_subtype_4(data, num_glyphs)
        elif subtable_format == 6:
            self._process_subtype_6(data, num_glyphs)
        elif subtable_format == 8:
            self._process_subtype_8(data, num_glyphs)
        elif subtable_format == 10:
            self._process_subtype_10(data, num_glyphs)
        elif subtable_format == 12:
            self._process_subtype_12(data, num_glyphs)
        elif subtable_format == 13:
            self._process_subtype_13(data, num_glyphs)
        elif subtable_format == 14:
            self._process_subtype_14(data)
        else:
            raise OSError(f"Unknown cmap format:{subtable_format}")

    # ----- format 0 (byte encoding) -----

    def _process_subtype_0(self, data: TTFDataStream) -> None:
        glyph_mapping = data.read_bytes(256)
        self._glyph_id_to_character_code = self._new_glyph_id_to_character_code(256)
        self._character_code_to_glyph_id = {}
        for i, gb in enumerate(glyph_mapping):
            glyph_index = gb & 0xFF
            self._glyph_id_to_character_code[glyph_index] = i
            self._character_code_to_glyph_id[i] = glyph_index

    # ----- format 4 (segmented mapping for BMP) -----

    def _process_subtype_4(self, data: TTFDataStream, num_glyphs: int) -> None:
        seg_count_x2 = data.read_unsigned_short()
        seg_count = seg_count_x2 // 2
        data.read_unsigned_short()  # searchRange
        data.read_unsigned_short()  # entrySelector
        data.read_unsigned_short()  # rangeShift
        end_count = data.read_unsigned_short_array(seg_count)
        data.read_unsigned_short()  # reservedPad
        start_count = data.read_unsigned_short_array(seg_count)
        id_delta = data.read_unsigned_short_array(seg_count)
        id_range_offset_position = data.get_current_position()
        id_range_offset = data.read_unsigned_short_array(seg_count)

        self._character_code_to_glyph_id = {}
        max_glyph_id = 0
        for i in range(seg_count):
            start = start_count[i]
            end = end_count[i]
            if start == 65535 and end == 65535:
                continue
            delta = id_delta[i]
            range_offset = id_range_offset[i]
            segment_range_offset = id_range_offset_position + (i * 2) + range_offset
            for j in range(start, end + 1):
                if range_offset == 0:
                    glyph_id = (j + delta) & 0xFFFF
                    if glyph_id >= num_glyphs:
                        _LOG.warning("Format 4 cmap contains an invalid glyph index")
                        continue
                    if glyph_id > max_glyph_id:
                        max_glyph_id = glyph_id
                    self._character_code_to_glyph_id[j] = glyph_id
                else:
                    glyph_offset = segment_range_offset + ((j - start) * 2)
                    data.seek(glyph_offset)
                    glyph_index = data.read_unsigned_short()
                    if glyph_index != 0:
                        glyph_index = (glyph_index + delta) & 0xFFFF
                        if glyph_index >= num_glyphs:
                            _LOG.warning("Format 4 cmap contains an invalid glyph index")
                            continue
                        if glyph_index > max_glyph_id:
                            max_glyph_id = glyph_index
                        self._character_code_to_glyph_id[j] = glyph_index

        if not self._character_code_to_glyph_id:
            _LOG.warning("cmap format 4 subtable is empty")
            return
        self._build_glyph_id_to_character_code_lookup(max_glyph_id)

    # ----- format 6 (trimmed table mapping) -----

    def _process_subtype_6(self, data: TTFDataStream, num_glyphs: int) -> None:
        first_code = data.read_unsigned_short()
        entry_count = data.read_unsigned_short()
        if entry_count == 0:
            return
        self._character_code_to_glyph_id = {}
        glyph_id_array = data.read_unsigned_short_array(entry_count)
        max_glyph_id = 0
        for i in range(entry_count):
            if glyph_id_array[i] > max_glyph_id:
                max_glyph_id = glyph_id_array[i]
            self._character_code_to_glyph_id[first_code + i] = glyph_id_array[i]
        self._build_glyph_id_to_character_code_lookup(max_glyph_id)

    # ----- format 8 (mixed 16-/32-bit coverage) -----

    def _process_subtype_8(self, data: TTFDataStream, num_glyphs: int) -> None:
        # is32: 8192 bytes (= 65536 bits), one bit per BMP code unit indicating
        # whether that unit is the high half of a surrogate pair. We read but do
        # not need to interpret it: groups carry full 32-bit start/end codes.
        data.read_bytes(8192)
        nb_groups = data.read_unsigned_int()
        self._character_code_to_glyph_id = {}
        max_glyph_id = 0
        for _ in range(nb_groups):
            first_code = data.read_unsigned_int()
            end_code = data.read_unsigned_int()
            start_glyph = data.read_unsigned_int()
            if first_code > 0x0010FFFF or 0xD800 <= first_code <= 0xDFFF:
                raise OSError(f"Invalid character code 0x{first_code:X}")
            if (
                (end_code > 0 and end_code < first_code)
                or end_code > 0x0010FFFF
                or 0xD800 <= end_code <= 0xDFFF
            ):
                raise OSError(f"Invalid character code 0x{end_code:X}")
            for j in range(end_code - first_code + 1):
                glyph_index = start_glyph + j
                if glyph_index >= num_glyphs:
                    _LOG.warning("Format 8 cmap contains an invalid glyph index")
                    break
                if glyph_index > max_glyph_id:
                    max_glyph_id = glyph_index
                self._character_code_to_glyph_id[first_code + j] = glyph_index
        if self._character_code_to_glyph_id:
            self._build_glyph_id_to_character_code_lookup(max_glyph_id)

    # ----- format 10 (trimmed array — UCS-4) -----

    def _process_subtype_10(self, data: TTFDataStream, num_glyphs: int) -> None:
        start_char_code = data.read_unsigned_int()
        num_chars = data.read_unsigned_int()
        if num_chars == 0:
            return
        self._character_code_to_glyph_id = {}
        max_glyph_id = 0
        for i in range(num_chars):
            glyph_id = data.read_unsigned_short()
            if glyph_id == 0:
                continue
            if glyph_id >= num_glyphs:
                _LOG.warning("Format 10 cmap contains an invalid glyph index")
                continue
            if glyph_id > max_glyph_id:
                max_glyph_id = glyph_id
            self._character_code_to_glyph_id[start_char_code + i] = glyph_id
        if self._character_code_to_glyph_id:
            self._build_glyph_id_to_character_code_lookup(max_glyph_id)

    # ----- format 12 (segmented coverage UCS-4) -----

    def _process_subtype_12(self, data: TTFDataStream, num_glyphs: int) -> None:
        max_glyph_id = 0
        nb_groups = data.read_unsigned_int()
        self._glyph_id_to_character_code = self._new_glyph_id_to_character_code(num_glyphs)
        self._character_code_to_glyph_id = {}
        if num_glyphs == 0:
            _LOG.warning("subtable has no glyphs")
            return
        for _ in range(nb_groups):
            first_code = data.read_unsigned_int()
            end_code = data.read_unsigned_int()
            start_glyph = data.read_unsigned_int()

            if first_code > 0x0010FFFF or 0xD800 <= first_code <= 0xDFFF:
                raise OSError(f"Invalid character code 0x{first_code:X}")
            if (
                (end_code > 0 and end_code < first_code)
                or end_code > 0x0010FFFF
                or 0xD800 <= end_code <= 0xDFFF
            ):
                raise OSError(f"Invalid character code 0x{end_code:X}")

            for j in range(end_code - first_code + 1):
                glyph_index = start_glyph + j
                if glyph_index >= num_glyphs:
                    _LOG.warning("Format 12 cmap contains an invalid glyph index")
                    break
                if first_code + j > 0x10FFFF:
                    _LOG.warning("Format 12 cmap contains character beyond UCS-4")
                if glyph_index > max_glyph_id:
                    max_glyph_id = glyph_index
                self._character_code_to_glyph_id[first_code + j] = glyph_index
        self._build_glyph_id_to_character_code_lookup(max_glyph_id)

    # ----- format 13 (many-to-one mappings) -----

    def _process_subtype_13(self, data: TTFDataStream, num_glyphs: int) -> None:
        nb_groups = data.read_unsigned_int()
        self._character_code_to_glyph_id = {}
        if num_glyphs == 0:
            _LOG.warning("subtable has no glyphs")
            return
        max_glyph_id = 0
        for _ in range(nb_groups):
            first_code = data.read_unsigned_int()
            end_code = data.read_unsigned_int()
            glyph_id = data.read_unsigned_int()
            if first_code > 0x0010FFFF or 0xD800 <= first_code <= 0xDFFF:
                raise OSError(f"Invalid character code 0x{first_code:X}")
            if (
                (end_code > 0 and end_code < first_code)
                or end_code > 0x0010FFFF
                or 0xD800 <= end_code <= 0xDFFF
            ):
                raise OSError(f"Invalid character code 0x{end_code:X}")
            if glyph_id >= num_glyphs:
                _LOG.warning("Format 13 cmap contains an invalid glyph index")
                continue
            if glyph_id > max_glyph_id:
                max_glyph_id = glyph_id
            # ALL codes in [first_code, end_code] map to the same glyph_id
            for code in range(first_code, end_code + 1):
                self._character_code_to_glyph_id[code] = glyph_id
        if self._character_code_to_glyph_id:
            self._build_glyph_id_to_character_code_lookup(max_glyph_id)

    # ----- format 14 (Unicode Variation Sequences) -----

    def _process_subtype_14(self, data: TTFDataStream) -> None:
        # Subtable layout (see OpenType spec 'cmap' format 14):
        #   uint32  numVarSelectorRecords
        #   N times:
        #     uint24 varSelector
        #     uint32 defaultUVSOffset   (0 if absent)
        #     uint32 nonDefaultUVSOffset (0 if absent)
        # Offsets are relative to the start of the format-14 subtable, *which
        # begins at the format word*. We've already consumed the 6-byte header
        # (format uint16 + length uint32), so the subtable start is six bytes
        # before our current position.
        # The numVarSelectorRecords field has been consumed by init_subtable
        # — wait, no: format-14 path reads only ``length`` in init_subtable, so
        # the next read here is ``numVarSelectorRecords``.
        subtable_start = data.get_current_position() - 6
        num_records = data.read_unsigned_int()

        records: list[tuple[int, int, int]] = []
        for _ in range(num_records):
            var_selector = self._read_uint24(data)
            default_uvs_offset = data.read_unsigned_int()
            non_default_uvs_offset = data.read_unsigned_int()
            records.append((var_selector, default_uvs_offset, non_default_uvs_offset))

        self._uvs_mapping = {}
        self._default_uvs = []
        for var_selector, default_off, non_default_off in records:
            if default_off != 0:
                data.seek(subtable_start + default_off)
                num_unicode_value_ranges = data.read_unsigned_int()
                for _ in range(num_unicode_value_ranges):
                    start_unicode = self._read_uint24(data)
                    additional_count = data.read_unsigned_byte()
                    end_unicode = start_unicode + additional_count
                    self._default_uvs.append(
                        (var_selector, start_unicode, end_unicode)
                    )
            if non_default_off != 0:
                data.seek(subtable_start + non_default_off)
                num_uvs_mappings = data.read_unsigned_int()
                for _ in range(num_uvs_mappings):
                    unicode_value = self._read_uint24(data)
                    glyph_id = data.read_unsigned_short()
                    self._uvs_mapping[(unicode_value, var_selector)] = glyph_id

    @staticmethod
    def _read_uint24(data: TTFDataStream) -> int:
        b1 = data.read_unsigned_byte()
        b2 = data.read_unsigned_byte()
        b3 = data.read_unsigned_byte()
        return (b1 << 16) | (b2 << 8) | b3

    def get_glyph_id_uvs(self, code_point: int, variation_selector: int) -> int:
        """Return the glyph for ``(code_point, variation_selector)``.

        For format-14 subtables only. Returns 0 if the pair is not mapped and
        is not a default UVS entry; for default UVS pairs the caller should
        fall back to the regular ``get_glyph_id(code_point)``.
        """
        gid = self._uvs_mapping.get((code_point, variation_selector), 0)
        if gid != 0:
            return gid
        for sel, start, end in self._default_uvs:
            if sel == variation_selector and start <= code_point <= end:
                # Default UVS: caller should use the base glyph.
                return 0
        return 0

    def getGlyphIdUVS(self, code_point: int, variation_selector: int) -> int:  # noqa: N802
        return self.get_glyph_id_uvs(code_point, variation_selector)

    def has_uvs(self) -> bool:
        """Return ``True`` if this subtable carries UVS (format-14) data."""
        return bool(self._uvs_mapping) or bool(self._default_uvs)

    def hasUVS(self) -> bool:  # noqa: N802 - upstream Java name
        return self.has_uvs()

    # ----- format 2 (high-byte mapping through table — DBCS) -----

    def _process_subtype_2(self, data: TTFDataStream, num_glyphs: int) -> None:
        sub_header_keys = [0] * 256
        max_sub_header_index = 0
        for i in range(256):
            sub_header_keys[i] = data.read_unsigned_short()
            v = sub_header_keys[i] // 8
            if v > max_sub_header_index:
                max_sub_header_index = v

        sub_headers: list[tuple[int, int, int, int]] = []
        for i in range(max_sub_header_index + 1):
            first_code = data.read_unsigned_short()
            entry_count = data.read_unsigned_short()
            id_delta = data.read_signed_short()
            id_range_offset = (
                data.read_unsigned_short()
                - (max_sub_header_index + 1 - i - 1) * 8
                - 2
            )
            sub_headers.append((first_code, entry_count, id_delta, id_range_offset))

        start_glyph_index_offset = data.get_current_position()
        self._glyph_id_to_character_code = self._new_glyph_id_to_character_code(num_glyphs)
        self._character_code_to_glyph_id = {}
        if num_glyphs == 0:
            _LOG.warning("subtable has no glyphs")
            return
        logged: set[int] = set()
        max_logging_reached = False
        for i in range(max_sub_header_index + 1):
            first_code, entry_count, id_delta, id_range_offset = sub_headers[i]
            data.seek(start_glyph_index_offset + id_range_offset)
            for j in range(entry_count):
                char_code = (i << 8) + (first_code + j)
                p = data.read_unsigned_short()
                if p > 0:
                    p = (p + id_delta) % 65536
                    if p < 0:
                        p += 65536
                if p >= num_glyphs:
                    if not max_logging_reached and p not in logged:
                        _LOG.warning(
                            "glyphId %d for charcode %d ignored, numGlyphs is %d",
                            p, char_code, num_glyphs,
                        )
                        logged.add(p)
                        if len(logged) > 10:
                            max_logging_reached = True
                    continue
                self._glyph_id_to_character_code[p] = char_code
                self._character_code_to_glyph_id[char_code] = p

    # ----- helpers -----

    @staticmethod
    def _new_glyph_id_to_character_code(size: int) -> list[int]:
        return [-1] * size

    def _build_glyph_id_to_character_code_lookup(self, max_glyph_id: int) -> None:
        self._glyph_id_to_character_code = self._new_glyph_id_to_character_code(max_glyph_id + 1)
        for code, gid in self._character_code_to_glyph_id.items():
            if self._glyph_id_to_character_code[gid] == -1:
                self._glyph_id_to_character_code[gid] = code
            else:
                mapped = self._glyph_id_to_character_code_multiple.get(gid)
                if mapped is None:
                    mapped = [self._glyph_id_to_character_code[gid]]
                    self._glyph_id_to_character_code_multiple[gid] = mapped
                    # Sentinel: -2_147_483_648 (Java Integer.MIN_VALUE) marks "see multi map"
                    self._glyph_id_to_character_code[gid] = -2_147_483_648
                mapped.append(code)

    # ---- public ----
    def get_platform_id(self) -> int:
        return self._platform_id

    def getPlatformId(self) -> int:  # noqa: N802 - upstream Java name
        return self.get_platform_id()

    def set_platform_id(self, value: int) -> None:
        self._platform_id = value

    def setPlatformId(self, value: int) -> None:  # noqa: N802 - upstream Java name
        self.set_platform_id(value)

    def get_platform_encoding_id(self) -> int:
        return self._platform_encoding_id

    def getPlatformEncodingId(self) -> int:  # noqa: N802 - upstream Java name
        return self.get_platform_encoding_id()

    def set_platform_encoding_id(self, value: int) -> None:
        self._platform_encoding_id = value

    def setPlatformEncodingId(self, value: int) -> None:  # noqa: N802
        self.set_platform_encoding_id(value)

    def get_glyph_id(self, code_point_at: int) -> int:
        return self._character_code_to_glyph_id.get(code_point_at, 0)

    def getGlyphId(self, code_point_at: int) -> int:  # noqa: N802 - upstream Java name
        return self.get_glyph_id(code_point_at)

    def _get_char_code(self, gid: int) -> int:
        if (
            gid < 0
            or self._glyph_id_to_character_code is None
            or gid >= len(self._glyph_id_to_character_code)
        ):
            return -1
        return self._glyph_id_to_character_code[gid]

    def getCharCode(self, gid: int) -> int:  # noqa: N802 - upstream Java name
        return self._get_char_code(gid)

    def get_char_codes(self, gid: int) -> list[int] | None:
        code = self._get_char_code(gid)
        if code == -1:
            return None
        if code == -2_147_483_648:
            mapped = self._glyph_id_to_character_code_multiple.get(gid)
            if mapped is not None:
                return sorted(mapped)
            return None
        return [code]

    def getCharCodes(self, gid: int) -> list[int] | None:  # noqa: N802
        return self.get_char_codes(gid)

    def __repr__(self) -> str:
        return f"{{{self._platform_id} {self._platform_encoding_id}}}"
