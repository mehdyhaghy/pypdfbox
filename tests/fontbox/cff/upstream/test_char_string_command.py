"""Ported upstream JUnit tests for ``CharStringCommand``.

Translated from
``pdfbox/fontbox/src/test/java/org/apache/fontbox/cff/CharStringCommandTest.java``.
"""

from __future__ import annotations

from pypdfbox.fontbox.cff import (
    CharStringCommand,
    Key,
    Type1KeyWord,
    Type2KeyWord,
)


def test_key() -> None:
    # Mirrors CharStringCommandTest.testKey.
    assert Key.value_of_key(1) is Key.HSTEM
    assert Key.value_of_key(12) is Key.ESCAPE
    assert Key.value_of_key(12, 0) is Key.DOTSECTION
    assert Key.value_of_key(12, 3) is Key.AND
    assert Key.value_of_key(13) is Key.HSBW


def test_char_string_command() -> None:
    # Mirrors CharStringCommandTest.testCharStringCommand.
    cmd1 = CharStringCommand.get_instance(1)
    assert cmd1.get_type1_key_word() is Type1KeyWord.HSTEM
    assert cmd1.get_type2_key_word() is Type2KeyWord.HSTEM
    assert str(cmd1) == "HSTEM|"

    cmd_12_0 = CharStringCommand.get_instance(12, 0)
    assert cmd_12_0.get_type1_key_word() is Type1KeyWord.DOTSECTION
    assert cmd_12_0.get_type2_key_word() is None
    assert str(cmd_12_0) == "DOTSECTION|"

    cmd_12_3 = CharStringCommand.get_instance([12, 3])
    assert cmd_12_3.get_type1_key_word() is None
    assert cmd_12_3.get_type2_key_word() is Type2KeyWord.AND
    assert str(cmd_12_3) == "AND|"


def test_unknown_char_string_command() -> None:
    # Mirrors CharStringCommandTest.testUnknownCharStringCommand.
    cmd_unknown = CharStringCommand.get_instance(99)
    assert str(cmd_unknown) == "unknown command|"
