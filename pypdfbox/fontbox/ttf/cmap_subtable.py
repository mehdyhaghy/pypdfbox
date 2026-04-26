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

    Cluster #1 implements formats 0, 4, 6, and 12 (the formats present in
    >99% of real-world fonts). Format 2 (DBCS subheader) is also implemented
    so we don't break on legacy CJK TrueType. Formats 8, 10, 13, 14 raise
    :class:`NotImplementedError` pointing at fontbox cluster #3.
    """

    def __init__(self) -> None:
        self._platform_id: int = 0
        self._platform_encoding_id: int = 0
        self._sub_table_offset: int = 0
        self._glyph_id_to_character_code: list[int] | None = None
        self._glyph_id_to_character_code_multiple: dict[int, list[int]] = {}
        self._character_code_to_glyph_id: dict[int, int] = {}

    def init_data(self, data: TTFDataStream) -> None:
        self._platform_id = data.read_unsigned_short()
        self._platform_encoding_id = data.read_unsigned_short()
        self._sub_table_offset = data.read_unsigned_int()

    def init_subtable(self, cmap: CmapTable, num_glyphs: int, data: TTFDataStream) -> None:
        data.seek(cmap.get_offset() + self._sub_table_offset)
        subtable_format = data.read_unsigned_short()
        if subtable_format < 8:
            length = data.read_unsigned_short()  # noqa: F841
            version = data.read_unsigned_short()  # noqa: F841
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
        elif subtable_format == 12:
            self._process_subtype_12(data, num_glyphs)
        elif subtable_format in (8, 10, 13, 14):
            # PDFBox supports these but they are exotic; deferred to cluster #3
            # so we don't have to ship the full conformance tests yet.
            raise NotImplementedError(
                f"CMap format {subtable_format} — fontbox cluster #3"
            )
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
                    if glyph_id > max_glyph_id:
                        max_glyph_id = glyph_id
                    self._character_code_to_glyph_id[j] = glyph_id
                else:
                    glyph_offset = segment_range_offset + ((j - start) * 2)
                    data.seek(glyph_offset)
                    glyph_index = data.read_unsigned_short()
                    if glyph_index != 0:
                        glyph_index = (glyph_index + delta) & 0xFFFF
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

    def set_platform_id(self, value: int) -> None:
        self._platform_id = value

    def get_platform_encoding_id(self) -> int:
        return self._platform_encoding_id

    def set_platform_encoding_id(self, value: int) -> None:
        self._platform_encoding_id = value

    def get_glyph_id(self, code_point_at: int) -> int:
        return self._character_code_to_glyph_id.get(code_point_at, 0)

    def _get_char_code(self, gid: int) -> int:
        if (
            gid < 0
            or self._glyph_id_to_character_code is None
            or gid >= len(self._glyph_id_to_character_code)
        ):
            return -1
        return self._glyph_id_to_character_code[gid]

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

    def __repr__(self) -> str:
        return f"{{{self._platform_id} {self._platform_encoding_id}}}"
