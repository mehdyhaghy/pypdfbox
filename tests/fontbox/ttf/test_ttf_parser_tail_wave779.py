from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from pypdfbox.fontbox.ttf.glyph_table import GlyphTable
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.fontbox.ttf.true_type_font import TrueTypeFont
from pypdfbox.fontbox.ttf.ttf_data_stream import MemoryTTFDataStream
from pypdfbox.fontbox.ttf.ttf_parser import TTFParser


class _NonBytesReader:
    def read(self) -> str:
        return "not bytes"


class _MissingRequiredTableFont:
    def has_table(self, tag: str) -> bool:
        return tag != "cmap"


class _TagMap(dict[str, Any]):
    def __contains__(self, key: object) -> bool:
        return dict.__contains__(self, key)


class _NameTable:
    def getDebugName(self, _name_id: int) -> None:  # noqa: N802 - fontTools API
        return None


class _FakeTTFont:
    def __init__(self) -> None:
        self._tables = {"glyf": object()}

    def __getitem__(self, tag: str) -> object:
        return self._tables[tag]

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 - fontTools API
        return [".notdef", "A"]


class _FakeTrueTypeFont:
    def __init__(self) -> None:
        self._tt = _FakeTTFont()

    def get_number_of_glyphs(self) -> int:
        return 2

    def get_units_per_em(self) -> int:
        return 1000


def test_file_like_source_must_return_bytes() -> None:
    parser = TTFParser()

    with pytest.raises(TypeError, match="file-like source must yield bytes"):
        parser.parse(_NonBytesReader())  # type: ignore[arg-type]


def test_check_tables_reports_missing_required_tables() -> None:
    parser = TTFParser()

    with pytest.raises(OSError, match=r"\['cmap'\]"):
        parser._check_tables(_MissingRequiredTableFont())  # noqa: SLF001


def test_embedded_otf_check_tables_returns_after_shared_check() -> None:
    parser = OTFParser(is_embedded=True)

    parser._check_tables(_MissingRequiredTableFont())  # noqa: SLF001


def test_horizontal_metrics_returns_none_without_horizontal_header() -> None:
    font = object.__new__(TrueTypeFont)
    font._hmtx = None  # noqa: SLF001
    font._hhea = None  # noqa: SLF001
    font._tt = _TagMap({"hmtx": SimpleNamespace(metrics={})})  # noqa: SLF001

    assert font.get_horizontal_metrics() is None


def test_name_string_returns_none_when_name_record_missing() -> None:
    font = object.__new__(TrueTypeFont)
    font._tt = _TagMap({"name": _NameTable()})  # noqa: SLF001

    assert font._get_name_string(6) is None  # noqa: SLF001


def test_os2_windows_decodes_byte_vendor_id() -> None:
    font = object.__new__(TrueTypeFont)
    font._os2_resolved = False  # noqa: SLF001
    font._os2 = None  # noqa: SLF001
    font._tt = _TagMap(  # noqa: SLF001
        {
            "OS/2": SimpleNamespace(
                version=0,
                xAvgCharWidth=500,
                usWeightClass=400,
                usWidthClass=5,
                fsType=0,
                ySubscriptXSize=650,
                ySubscriptYSize=600,
                ySubscriptXOffset=0,
                ySubscriptYOffset=75,
                ySuperscriptXSize=650,
                ySuperscriptYSize=600,
                ySuperscriptXOffset=0,
                ySuperscriptYOffset=350,
                yStrikeoutSize=50,
                yStrikeoutPosition=250,
                sFamilyClass=0,
                panose=None,
                ulUnicodeRange1=1,
                ulUnicodeRange2=2,
                ulUnicodeRange3=3,
                ulUnicodeRange4=4,
                achVendID=b"TEST",
                fsSelection=64,
                usFirstCharIndex=32,
                usLastCharIndex=255,
                sTypoAscender=800,
                sTypoDescender=-200,
                sTypoLineGap=0,
                usWinAscent=900,
                usWinDescent=250,
            )
        }
    )

    os2 = font.get_os2_windows()

    assert os2 is not None
    assert os2.get_ach_vend_id() == "TEST"


def test_glyph_table_read_binds_fonttools_glyph_table() -> None:
    table = GlyphTable()

    table.read(_FakeTrueTypeFont(), MemoryTTFDataStream(b""))  # type: ignore[arg-type]

    assert table.get_initialized() is True
    assert table.get_glyph(1) is not None
