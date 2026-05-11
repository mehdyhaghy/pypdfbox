"""Tests for new ``pypdfbox.fontbox.type1`` ports."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.type1.token import Kind, Token
from pypdfbox.fontbox.type1.type1_char_string_reader import Type1CharStringReader


def test_token_text_and_kind() -> None:
    t = Token("42", Kind.INTEGER)
    assert t.get_text() == "42"
    assert t.get_kind() is Kind.INTEGER
    assert t.int_value() == 42


def test_token_float_value_tolerates_real_form() -> None:
    t = Token("1.5", Kind.REAL)
    assert t.float_value() == 1.5
    assert t.int_value() == 1


def test_token_boolean_value() -> None:
    assert Token("true", Kind.LITERAL).boolean_value() is True
    assert Token("false", Kind.LITERAL).boolean_value() is False


def test_token_charstring_carries_bytes() -> None:
    t = Token(b"\x01\x02\x03", Kind.CHARSTRING)
    assert t.get_data() == b"\x01\x02\x03"
    assert "CHARSTRING" in repr(t)


def test_type1_char_string_reader_is_abstract() -> None:
    class StubReader(Type1CharStringReader):
        def get_type1_char_string(self, name: str) -> object:
            return ("stub", name)

    reader = StubReader()
    assert reader.get_type1_char_string("A") == ("stub", "A")


def test_type1_char_string_reader_cannot_instantiate_without_impl() -> None:
    with pytest.raises(TypeError):
        Type1CharStringReader()  # type: ignore[abstract]
