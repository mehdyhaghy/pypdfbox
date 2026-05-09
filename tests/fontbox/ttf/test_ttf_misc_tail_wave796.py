from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.fontbox.ttf import (
    GlyphData,
    GlyphTable,
    OTFParser,
    TrueTypeFont,
    TTFParser,
    TTFTable,
)
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream


class _FakeTTFont:
    def __init__(
        self,
        tables: dict[str, object] | None = None,
        glyph_order: list[str] | None = None,
    ) -> None:
        self._tables = tables or {}
        self._glyph_order = glyph_order or []
        self.close_count = 0

    def __contains__(self, tag: object) -> bool:
        return tag in self._tables

    def __getitem__(self, tag: str) -> object:
        return self._tables[tag]

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 - fontTools API
        return list(self._glyph_order)

    def close(self) -> None:
        self.close_count += 1


def _font(tt: _FakeTTFont | None = None, raw: bytes = b"abcdef") -> TrueTypeFont:
    font = object.__new__(TrueTypeFont)
    font._tt = tt or _FakeTTFont()  # noqa: SLF001
    font._raw_bytes = raw  # noqa: SLF001
    font._table_map = None  # noqa: SLF001
    font._advance_widths = None  # noqa: SLF001
    font._closed = False  # noqa: SLF001
    return font


def _table(tag: str, offset: int, length: int) -> TTFTable:
    table = TTFTable()
    table.set_tag(tag)
    table.set_offset(offset)
    table.set_length(length)
    return table


def test_ttf_parser_scaler_type_edges_without_fonttools_construction() -> None:
    parser = TTFParser()

    with pytest.raises(OSError, match="SFNT stream too short"):
        parser._parse_data_stream(MemoryTTFDataStream(b"abc"))  # noqa: SLF001
    with pytest.raises(OSError, match="use OTFParser"):
        parser._check_scaler_type(0x4F54544F)  # noqa: SLF001

    parser._check_scaler_type(0x74727565)  # noqa: SLF001

    otf_parser = OTFParser()
    assert parser._allow_cff() is False  # noqa: SLF001
    assert otf_parser._allow_cff() is True  # noqa: SLF001
    otf_parser._check_scaler_type(0x00010000)  # noqa: SLF001
    with pytest.raises(OSError, match="expected 'OTTO'"):
        otf_parser._check_scaler_type(0x12345678)  # noqa: SLF001


def test_true_type_font_table_byte_helpers_clamp_valid_entries() -> None:
    font = _font(raw=b"0123456789")
    font._table_map = {"test": _table("test", 2, 5)}  # noqa: SLF001

    assert font.get_table_bytes("test") == b"23456"
    assert font.get_table_n_bytes("test", -10) == b""
    assert font.get_table_n_bytes("test", 99) == b"23456"


def test_true_type_font_glyph_name_helpers_and_width_lookup() -> None:
    hmtx = SimpleNamespace(metrics={".notdef": (500, 0), "A": (610, 20)})
    font = _font(_FakeTTFont({"hmtx": hmtx}, [".notdef", "A"]))

    assert font.name_to_gid("") == 0
    assert font.name_to_gid("A") == 1
    assert font.has_glyph("A") is True
    assert font.has_glyph(".notdef") is False
    assert font.get_width("A") == 610.0
    assert font.get_width("missing") == 0.0


def test_true_type_font_get_path_accepts_glyph_names() -> None:
    font = _font(_FakeTTFont(glyph_order=[".notdef", "A"]))

    def _get_glyph(gid: int) -> Any:
        return SimpleNamespace(get_path=lambda: ("path", gid))

    font.get_glyph = _get_glyph  # type: ignore[method-assign]

    assert font.get_path("A") == ("path", 1)
    assert font.get_path(".notdef") is None
    assert font.get_path("missing") is None


def test_true_type_font_close_is_idempotent() -> None:
    tt = _FakeTTFont()
    font = _font(tt)

    assert font.__enter__() is font
    font.__exit__(None, None, None)
    font.close()

    assert font._closed is True  # noqa: SLF001
    assert tt.close_count == 1


def test_glyph_table_set_glyphs_counts_cache_and_clears() -> None:
    table = GlyphTable()

    table.set_glyphs([GlyphData(), None, GlyphData()])  # type: ignore[list-item]

    assert table._cached == 2  # noqa: SLF001
    assert table._glyphs is not None  # noqa: SLF001

    table.set_glyphs(None)

    assert table._cached == 0  # noqa: SLF001
    assert table._glyphs is None  # noqa: SLF001
