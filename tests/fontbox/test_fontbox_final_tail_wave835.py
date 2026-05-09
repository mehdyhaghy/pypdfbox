from __future__ import annotations

import logging

import pytest

from pypdfbox.fontbox.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_parser import CMapParser, _increment
from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_INTEGER,
    TOKEN_LITERAL,
    Type1Lexer,
    Type1Parser,
)


def test_wave835_use_cmap_lifts_shorter_and_longer_codespaces() -> None:
    parent = CMap("parent")
    parent.add_codespace_range(b"\x00", b"\x7f")
    parent.add_codespace_range(b"\x81\x02\x03\x00", b"\x81\x02\x03\xff")
    parent.add_base_font_character(b"\x81\x02\x03\x04", "tail")

    child = CMap("child")
    child.add_codespace_range(b"\x80\x00", b"\x80\xff")

    child.use_cmap(parent)

    assert child.get_min_code_length() == 1
    assert child.get_max_code_length() == 4
    assert child.read_code(b"\x81\x02\x03\x04") == (0x81020304, 4)
    assert child.get_codes_from_unicode("tail") == b"\x81\x02\x03\x04"


def test_wave835_cmap_parser_odd_hex_digit_and_metadata_dict() -> None:
    cmap = CMapParser().parse(
        b"""
        /CIDSystemInfo << /Registry (Adobe) /Ordering (Tail) /Supplement 7 >> def
        /CMapName /Tail-CMap def
        1 beginbfchar
        <A> /GlyphName
        endbfchar
        endcmap
        """
    )

    assert cmap.get_registry() == "Adobe"
    assert cmap.get_ordering() == "Tail"
    assert cmap.get_supplement() == 7
    assert cmap.get_name() == "Tail-CMap"
    assert cmap.to_unicode_bytes(b"\xa0") == "GlyphName"


class _CarriesPastHighByte(int):
    def __gt__(self, other: object) -> bool:
        return int(self) == 0 and other == 0

    def __sub__(self, other: object) -> int:
        assert other == 1
        return -1


def test_wave835_increment_handles_defensive_negative_carry_position() -> None:
    value = bytearray(b"\xff")

    assert _increment(value, _CarriesPastHighByte(0), use_strict_mode=False) is True  # type: ignore[arg-type]
    assert value == b"\x00"


class _BeyondUCS4Start:
    def __gt__(self, _other: object) -> bool:
        return False

    def __ge__(self, _other: object) -> bool:
        return False

    def __rsub__(self, _other: object) -> int:
        return 0

    def __add__(self, other: object) -> int:
        return 0x110000 + int(other)


class _Format12BeyondUCS4Data:
    def __init__(self) -> None:
        self._values = iter([1, _BeyondUCS4Start(), 0, 1])

    def read_unsigned_int(self) -> object:
        return next(self._values)


def test_wave835_format12_logs_beyond_ucs4_after_defensive_add(
    caplog: pytest.LogCaptureFixture,
) -> None:
    subtable = CmapSubtable()

    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable"):
        subtable._process_subtype_12(_Format12BeyondUCS4Data(), num_glyphs=2)  # type: ignore[arg-type]  # noqa: SLF001

    assert "Format 12 cmap contains character beyond UCS-4" in caplog.text


def test_wave835_type1_encoding_array_eof_returns_notdef_defaults() -> None:
    parser = Type1Parser()

    assert parser._read_encoding_array(Type1Lexer(""), 4) == [  # noqa: SLF001
        ".notdef",
        ".notdef",
        ".notdef",
        ".notdef",
    ]


class _PeekedLiteralDisappearsLexer:
    def __init__(self) -> None:
        self._returned_length = False

    def next_token(self) -> tuple[str, object] | None:
        if not self._returned_length:
            self._returned_length = True
            return TOKEN_INTEGER, 1
        return None

    def peek_token(self) -> tuple[str, object] | None:
        return TOKEN_LITERAL, "A"


def test_wave835_type1_charstrings_returns_when_peeked_name_disappears() -> None:
    parser = Type1Parser()
    charstrings: dict[str, bytes] = {}

    parser._read_charstrings(_PeekedLiteralDisappearsLexer(), charstrings, len_iv=4)  # type: ignore[arg-type]  # noqa: SLF001

    assert charstrings == {}
