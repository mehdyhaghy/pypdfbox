"""Wave 1348 coverage-boost tests for ``pypdfbox.fontbox.ttf.cmap_subtable``.

Targets the backwards-compatible underscore-prefixed alias methods that
were never exercised:

  * ``_process_subtype_0`` / ``_4`` / ``_6`` / ``_8`` / ``_10`` / ``_13``
    / ``_14`` (lines 110, 165, 189, 225, 250, 324, 371).
  * ``_new_glyph_id_to_character_code`` (line 471).
  * ``_get_char_code`` (line 533).
"""
from __future__ import annotations

import struct

from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream

# ---------- subtype-method aliases ----------


def test_process_subtype_0_alias_delegates_to_public_form() -> None:
    sub = CmapSubtable()
    # 256 byte mapping table.
    data = MemoryTTFDataStream(bytes(range(256)))
    sub._process_subtype_0(data)  # noqa: SLF001 — alias under test
    assert sub.get_glyph_id(0) == 0
    assert sub.get_glyph_id(1) == 1
    assert sub.get_glyph_id(255) == 255


def _format4_min_bytes() -> bytes:
    # Minimal format-4 body: 1 segment from 0..0 with idDelta=0 mapping
    # code 0 -> glyph 0; endCodes ends with 0xFFFF sentinel.
    seg_count_x2 = 4  # 2 segments × 2 bytes
    search_range = 4
    entry_selector = 1
    range_shift = 0
    body = struct.pack(
        ">HHHH", seg_count_x2, search_range, entry_selector, range_shift
    )
    # endCode[2] (each uint16): 0, 0xFFFF
    body += struct.pack(">HH", 0, 0xFFFF)
    body += b"\x00\x00"  # reservedPad
    # startCode[2]: 0, 0xFFFF
    body += struct.pack(">HH", 0, 0xFFFF)
    # idDelta[2]: 0, 1  (last segment maps to glyph 0 via 0xFFFF+1=0)
    body += struct.pack(">hh", 0, 1)
    # idRangeOffset[2]: 0, 0
    body += struct.pack(">HH", 0, 0)
    return body


def test_process_subtype_4_alias_delegates_to_public_form() -> None:
    sub = CmapSubtable()
    data = MemoryTTFDataStream(_format4_min_bytes())
    sub._process_subtype_4(data, num_glyphs=256)  # noqa: SLF001
    # The 0 -> 0 entry has glyph_id 0 (which is filtered), so just verify
    # the call ran without raising.
    assert sub.get_glyph_id(0) in (0,)


def test_process_subtype_6_alias_delegates_to_public_form() -> None:
    sub = CmapSubtable()
    # firstCode, entryCount, glyphIdArray (3 entries: 1, 2, 3)
    payload = struct.pack(">HHHHH", 10, 3, 1, 2, 3)
    data = MemoryTTFDataStream(payload)
    sub._process_subtype_6(data, num_glyphs=16)  # noqa: SLF001
    assert sub.get_glyph_id(10) == 1
    assert sub.get_glyph_id(11) == 2
    assert sub.get_glyph_id(12) == 3


def test_process_subtype_8_alias_delegates_to_public_form() -> None:
    sub = CmapSubtable()
    is32 = b"\x00" * 8192
    body = is32 + struct.pack(">I", 1)  # nGroups = 1
    body += struct.pack(">III", 100, 102, 10)  # first, end, startGlyph
    data = MemoryTTFDataStream(body)
    sub._process_subtype_8(data, num_glyphs=64)  # noqa: SLF001
    assert sub.get_glyph_id(100) == 10
    assert sub.get_glyph_id(102) == 12


def test_process_subtype_10_alias_delegates_to_public_form() -> None:
    sub = CmapSubtable()
    payload = struct.pack(">IIHH", 50, 2, 5, 6)
    data = MemoryTTFDataStream(payload)
    sub._process_subtype_10(data, num_glyphs=16)  # noqa: SLF001
    assert sub.get_glyph_id(50) == 5
    assert sub.get_glyph_id(51) == 6


def test_process_subtype_13_alias_delegates_to_public_form() -> None:
    sub = CmapSubtable()
    body = struct.pack(">I", 1)  # nGroups
    body += struct.pack(">III", 200, 202, 7)  # first, end, glyph_id (same for all)
    data = MemoryTTFDataStream(body)
    sub._process_subtype_13(data, num_glyphs=16)  # noqa: SLF001
    assert sub.get_glyph_id(200) == 7
    assert sub.get_glyph_id(201) == 7
    assert sub.get_glyph_id(202) == 7


def test_process_subtype_14_alias_delegates_to_public_form() -> None:
    sub = CmapSubtable()
    # numVarSelectorRecords = 0 — minimal valid format-14 body.
    # The subtype-14 reader rewinds 6 bytes to align with the format
    # word, so we prepend a 6-byte header.
    payload = b"\x00" * 6 + struct.pack(">I", 0)
    data = MemoryTTFDataStream(payload)
    data.seek(6)  # simulate having read past the format-14 header
    sub._process_subtype_14(data)  # noqa: SLF001


# ---------- _new_glyph_id_to_character_code alias ----------


def test_new_glyph_id_to_character_code_alias() -> None:
    """Static alias mirrors the public form."""
    public = CmapSubtable.new_glyph_id_to_character_code(4)
    private = CmapSubtable._new_glyph_id_to_character_code(4)  # noqa: SLF001
    assert public == private == [-1, -1, -1, -1]


# ---------- _get_char_code alias ----------


def test_get_char_code_alias_delegates_to_public_form() -> None:
    sub = CmapSubtable()
    sub._character_code_to_glyph_id = {65: 1, 66: 2}  # noqa: SLF001
    sub.build_glyph_id_to_character_code_lookup(2)
    public = sub.get_char_code(1)
    private = sub._get_char_code(1)  # noqa: SLF001
    assert public == private
