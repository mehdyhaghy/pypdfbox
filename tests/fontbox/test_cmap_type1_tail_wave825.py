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


def test_wave825_use_cmap_updates_empty_child_code_length_bounds() -> None:
    child = CMap("child")
    parent = CMap("parent")
    parent.add_codespace_range(b"\x81\x40", b"\x81\xff")

    child.use_cmap(parent)

    assert child.get_min_code_length() == 2
    assert child.get_max_code_length() == 2
    assert child.read_code(b"\x81\x41") == (0x8141, 2)


def test_wave825_cmap_rejects_stream_offset_and_bad_cid_range() -> None:
    cmap = CMap("tail")

    with pytest.raises(TypeError, match="offset is only supported"):
        cmap.read_code(object(), offset=1)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="equal length"):
        cmap.add_cid_range(b"\x01", b"\x00\x02", 7)


def test_wave825_parser_parse_chunk_merges_into_existing_cmap() -> None:
    base = CMap("base")
    parsed = CMapParser().parse_chunk(
        b"1 beginbfchar <01> <0041> endbfchar endcmap",
        base,
    )

    assert parsed is base
    assert base.to_unicode_bytes(b"\x01") == "A"
    assert base.get_codes_from_unicode("A") == b"\x01"


class _CarriesBelowZero(int):
    def __gt__(self, other: object) -> bool:
        return int(self) == 0 and other == 0

    def __sub__(self, other: object) -> int:
        assert other == 1
        return -1


def test_wave825_increment_defensive_negative_carry_exit() -> None:
    value = bytearray(b"\xff")

    assert _increment(value, _CarriesBelowZero(0), use_strict_mode=False) is True  # type: ignore[arg-type]
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


def test_wave825_format12_logs_defensive_beyond_ucs4_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    subtable = CmapSubtable()

    with caplog.at_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable"):
        subtable._process_subtype_12(_Format12BeyondUCS4Data(), num_glyphs=2)  # type: ignore[arg-type]  # noqa: SLF001

    assert "Format 12 cmap contains character beyond UCS-4" in caplog.text


def test_wave825_type1_encoding_array_empty_input_returns_defaults() -> None:
    parser = Type1Parser()

    assert parser._read_encoding_array(Type1Lexer(""), 3) == [  # noqa: SLF001
        ".notdef",
        ".notdef",
        ".notdef",
    ]


class _LiteralVanishesAfterPeekLexer:
    def __init__(self) -> None:
        self._returned_length = False

    def next_token(self) -> tuple[str, object] | None:
        if not self._returned_length:
            self._returned_length = True
            return TOKEN_INTEGER, 1
        return None

    def peek_token(self) -> tuple[str, object] | None:
        return TOKEN_LITERAL, "A"


def test_wave825_type1_charstrings_tolerates_name_disappearing_after_peek() -> None:
    parser = Type1Parser()
    charstrings: dict[str, bytes] = {}

    parser._read_charstrings(_LiteralVanishesAfterPeekLexer(), charstrings, len_iv=4)  # type: ignore[arg-type]  # noqa: SLF001

    assert charstrings == {}
