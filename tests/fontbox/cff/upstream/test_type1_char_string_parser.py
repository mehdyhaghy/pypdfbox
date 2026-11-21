"""Port of upstream ``Type1CharStringParserTest`` from
``fontbox/src/test/java/org/apache/fontbox/cff/Type1CharStringParserTest.java``
(PDFBOX-6308: subroutine nesting limit)."""

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type1_char_string_parser import Type1CharStringParser

CALLSUBR = 10
RETURN = 11
ENDCHAR = 14
RMOVETO = 21
# operand 0
NUMBER_0 = 139
# operand 100
NUMBER_100 = 239
# largest operand with a single byte encoding
MAX_SINGLE_BYTE_NUMBER = 107

COMMAND_RMOVETO = CharStringCommand.get_instance(RMOVETO)
COMMAND_ENDCHAR = CharStringCommand.get_instance(ENDCHAR)


def _create_subr_chain(length: int) -> list[bytes]:
    """Creates subroutines where each one calls the next one and the last one
    contains the path."""
    # the subroutine numbers must fit the single byte operand encoding
    assert length - 1 <= MAX_SINGLE_BYTE_NUMBER
    subrs = [bytes([NUMBER_0 + i, CALLSUBR, RETURN]) for i in range(1, length)]
    subrs.append(bytes([NUMBER_100, NUMBER_100, RMOVETO, RETURN]))
    return subrs


def test_subr_calling_itself() -> None:
    loop = bytes([NUMBER_0, CALLSUBR])
    subrs = [loop]
    parser = Type1CharStringParser("test")
    with pytest.raises(OSError):
        parser.parse(loop, subrs, ".notdef")


def test_subrs_calling_each_other() -> None:
    first = bytes([NUMBER_0 + 1, CALLSUBR])
    second = bytes([NUMBER_0, CALLSUBR])
    subrs = [first, second]
    parser = Type1CharStringParser("test")
    with pytest.raises(OSError):
        parser.parse(first, subrs, ".notdef")


def test_subrs_nested_up_to_limit() -> None:
    subrs = _create_subr_chain(Type1CharStringParser.MAX_SUBR_NESTING)
    char_string = bytes([NUMBER_0, CALLSUBR, ENDCHAR])
    sequence = Type1CharStringParser("test").parse(char_string, subrs, "a")
    assert sequence == [100, 100, COMMAND_RMOVETO, COMMAND_ENDCHAR]


def test_subrs_nested_beyond_limit() -> None:
    subrs = _create_subr_chain(Type1CharStringParser.MAX_SUBR_NESTING + 1)
    char_string = bytes([NUMBER_0, CALLSUBR, ENDCHAR])
    parser = Type1CharStringParser("test")
    with pytest.raises(OSError):
        parser.parse(char_string, subrs, "a")
