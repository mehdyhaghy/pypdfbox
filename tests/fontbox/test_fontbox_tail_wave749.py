from __future__ import annotations

import io
import logging
import struct
from typing import cast

import pytest

from pypdfbox.fontbox.cmap.bf_char_range import BFCharRange
from pypdfbox.fontbox.cmap.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_parser import CMapParser, _increment
from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.ttf.glyph_data import GlyphData
from pypdfbox.fontbox.ttf.glyph_table import GlyphTable
from pypdfbox.fontbox.ttf.name_record import NameRecord
from pypdfbox.fontbox.ttf.naming_table import NamingTable
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


def _read_name_table(raw: bytes) -> NamingTable:
    blob = (
        struct.pack(">HHH", 0, 1, 18)
        + struct.pack(
            ">HHHHHH",
            NameRecord.PLATFORM_MACINTOSH,
            NameRecord.ENCODING_MACINTOSH_ROMAN,
            NameRecord.LANGUAGE_MACINTOSH_ENGLISH,
            NameRecord.NAME_FONT_FAMILY_NAME,
            len(raw),
            0,
        )
        + raw
    )
    table = NamingTable()
    table.set_offset(0)
    table.set_length(len(blob))
    table.read(cast(TrueTypeFont, object()), MemoryTTFDataStream(blob))
    return table


def test_bf_char_range_empty_target_stays_empty_when_incremented() -> None:
    bfrange = BFCharRange(b"\x01", b"\x02", target="")

    assert [entry.get_unicode() for entry in bfrange] == ["", ""]


def test_cmap_stream_fallback_breaks_when_extended_code_is_truncated(
    caplog: pytest.LogCaptureFixture,
) -> None:
    cmap = CMap("truncated-extension")
    cmap.add_codespace_range(b"\x00", b"\x7f")
    cmap.add_codespace_range(b"\x81\x40", b"\x81\xff")

    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.cmap.cmap"):
        assert cmap.read_code(io.BytesIO(b"\x82")) == 0x82

    assert "Invalid character code sequence 0x82 0x00" in caplog.text


def test_cmap_use_cmap_updates_child_min_and_max_lengths() -> None:
    parent = CMap("parent")
    parent.add_codespace_range(b"\x00\x00", b"\xff\xff")
    parent.add_cid_mapping(b"\x20", 20)

    shorter_child = CMap("shorter-child")
    shorter_child.add_codespace_range(b"\x00", b"\x7f")
    shorter_child.use_cmap(parent)

    assert shorter_child.get_min_code_length() == 1
    assert shorter_child.get_max_code_length() == 2

    child = CMap("child")
    child.add_codespace_range(b"\x01\x02\x03", b"\x01\x02\xff")
    child.use_cmap(parent)

    assert child.get_min_code_length() == 2
    assert child.get_max_code_length() == 3
    assert child.get_min_cid_length() == 1
    assert child.get_max_cid_length() == 1
    assert child.to_cid_bytes(b"\x20") == 20


def test_cmap_parser_skips_reversed_notdef_ranges_and_reports_bad_byte_token() -> None:
    cmap = CMapParser().parse(
        b"""
        1 beginnotdefrange
        <02> <01> 7
        endnotdefrange
        endcmap
        """
    )
    assert cmap.has_cid_mapping() is False

    with pytest.raises(OSError, match="invalid type for next token"):
        CMapParser().parse(b"1 begincodespacerange <00> 7 endcodespacerange")


def test_cmap_parser_increment_reports_leading_overflow_and_latin1_single_byte() -> None:
    assert _increment(bytearray(b""), -1, use_strict_mode=False) is False
    one_byte = CMapParser().parse(
        b"1 beginbfchar <41> <ff> endbfchar endcmap"
    )

    assert one_byte.to_unicode_bytes(b"A") == "\xff"


def test_cmap_format_2_suppresses_invalid_glyph_logging_after_threshold(
    caplog: pytest.LogCaptureFixture,
) -> None:
    max_sub_header_index = 10
    sub_header_keys = [0] * 256
    sub_header_keys[-1] = max_sub_header_index * 8
    payload = bytearray(struct.pack(">256H", *sub_header_keys))
    for i in range(max_sub_header_index + 1):
        raw_range_offset = (i * 2) + (max_sub_header_index - i) * 8 + 2
        payload.extend(struct.pack(">HHhH", 0, 1, 0, raw_range_offset))
    payload.extend(struct.pack(">11H", *range(50, 61)))

    subtable = CmapSubtable()

    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable"):
        subtable._process_subtype_2(MemoryTTFDataStream(bytes(payload)), num_glyphs=5)  # noqa: SLF001

    assert caplog.text.count("ignored, numGlyphs is 5") == 11
    assert subtable.get_glyph_id(0) == 0


def test_cmap_subtable_returns_none_for_missing_multiple_reverse_mapping() -> None:
    subtable = CmapSubtable()
    subtable._glyph_id_to_character_code = [-2_147_483_648]  # noqa: SLF001
    subtable._glyph_id_to_character_code_multiple = {}  # noqa: SLF001

    assert subtable.get_char_codes(0) is None


def test_naming_table_latin1_fallback_and_record_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_lookup_error(raw: bytes, charset: str) -> str:  # noqa: ARG001
        raise LookupError

    monkeypatch.setattr(NamingTable, "_decode_string", staticmethod(raise_lookup_error))

    table = _read_name_table(b"caf\xe9")

    assert table.get_name_records()[0].get_string() == "café"
    assert table.get_english_name(NameRecord.NAME_FONT_FAMILY_NAME) == "café"
    assert table.get_names_by_id(NameRecord.NAME_FONT_FAMILY_NAME) == table.get_name_records()
    assert table.language_ids(NameRecord.NAME_POSTSCRIPT_NAME) == []
    assert table.get_font_family(0x9999) is None


def test_glyph_table_large_bind_disables_cache_and_unbound_lookup_returns_none() -> None:
    class _Font:
        def __init__(self) -> None:
            self._tt = {"glyf": object()}

        def get_number_of_glyphs(self) -> int:
            return GlyphTable.MAX_CACHE_SIZE

        def get_units_per_em(self) -> int:
            return 1000

    class _TT:
        def __getitem__(self, key: str) -> object:
            assert key == "glyf"
            return object()

        def getGlyphOrder(self) -> list[str]:  # noqa: N802
            return [".notdef"] * GlyphTable.MAX_CACHE_SIZE

    unbound = GlyphTable()
    unbound._num_glyphs = 1  # noqa: SLF001
    assert unbound.get_glyph(0) is None

    font = _Font()
    font._tt = _TT()  # type: ignore[assignment]  # noqa: SLF001
    table = GlyphTable()
    table._bind(cast(TrueTypeFont, font))  # noqa: SLF001

    assert table._glyphs is None  # noqa: SLF001


def test_glyph_table_get_glyphs_uses_placeholder_when_lookup_returns_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = GlyphTable()
    table._num_glyphs = 1  # noqa: SLF001
    monkeypatch.setattr(table, "get_glyph", lambda gid: None)

    assert isinstance(table.get_glyphs()[0], GlyphData)
