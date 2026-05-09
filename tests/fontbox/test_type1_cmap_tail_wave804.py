from __future__ import annotations

import logging

from pypdfbox.fontbox.cmap import CMap
from pypdfbox.fontbox.cmap.cmap_parser import _increment
from pypdfbox.fontbox.ttf.cmap_subtable import CmapSubtable
from pypdfbox.fontbox.type1.type1_parser import (
    TOKEN_INTEGER,
    TOKEN_LITERAL,
    Type1Lexer,
    Type1Parser,
)


def test_type1_encoding_array_eof_returns_notdef_vector() -> None:
    parser = Type1Parser()

    assert parser._read_encoding_array(Type1Lexer(""), 2) == [".notdef", ".notdef"]  # noqa: SLF001


class _TruncatedCharStringLexer:
    def __init__(self) -> None:
        self._first_next = True

    def next_token(self) -> tuple[str, object] | None:
        if self._first_next:
            self._first_next = False
            return TOKEN_INTEGER, 1
        return None

    def peek_token(self) -> tuple[str, object] | None:
        return TOKEN_LITERAL, "A"


def test_type1_charstrings_tolerates_literal_disappearing_after_peek() -> None:
    parser = Type1Parser()
    out: dict[str, bytes] = {}

    parser._read_charstrings(_TruncatedCharStringLexer(), out, len_iv=4)  # type: ignore[arg-type]  # noqa: SLF001

    assert out == {}


def test_use_cmap_lifts_parent_code_length_bounds() -> None:
    child = CMap("child")
    parent = CMap("parent")
    parent.add_codespace_range(b"\x00\x00", b"\xff\xff")

    child.use_cmap(parent)

    assert child.get_max_code_length() == 2
    assert child.get_min_code_length() == 2


def test_increment_non_strict_all_ff_carries_through_high_byte() -> None:
    value = bytearray(b"\xff\xff")

    assert _increment(value, 1, use_strict_mode=False) is True
    assert value == b"\x00\x00"


class _BeyondUCS4Start:
    def __gt__(self, _other: object) -> bool:
        return False

    def __ge__(self, _other: object) -> bool:
        return False

    def __rsub__(self, _other: object) -> int:
        return 0

    def __add__(self, other: object) -> int:
        return 0x110000 + int(other)


class _Format12Data:
    def __init__(self) -> None:
        self._values = iter([1, _BeyondUCS4Start(), 0, 1])

    def read_unsigned_int(self) -> object:
        return next(self._values)


def test_format12_logs_character_beyond_ucs4_defensively(
    caplog: object,
) -> None:
    subtable = CmapSubtable()
    caplog.set_level(logging.WARNING, logger="pypdfbox.fontbox.ttf.cmap_subtable")

    subtable._process_subtype_12(_Format12Data(), num_glyphs=10)  # type: ignore[arg-type]  # noqa: SLF001

    assert "Format 12 cmap contains character beyond UCS-4" in caplog.text
