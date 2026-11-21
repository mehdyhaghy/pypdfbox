"""Port of upstream ``Type2CharStringParserTest`` from
``fontbox/src/test/java/org/apache/fontbox/cff/Type2CharStringParserTest.java``
(PDFBOX-6308: subroutine nesting limit)."""

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type2_char_string_parser import Type2CharStringParser

CALLSUBR = 10
RETURN = 11
ENDCHAR = 14
RMOVETO = 21
CALLGSUBR = 29
# operand 100
NUMBER_100 = 239
# operand -107, which is subroutine 0 in an index with less than 1240 subroutines
SUBR_0 = 32
# largest subroutine number with a single byte operand encoding
MAX_SINGLE_BYTE_SUBR = 214

COMMAND_RMOVETO = CharStringCommand.get_instance(RMOVETO)
COMMAND_ENDCHAR = CharStringCommand.get_instance(ENDCHAR)


def _create_subr_chain(length: int) -> list[bytes]:
    """Creates subroutines where each one calls the next one and the last one
    contains the path."""
    # the subroutine numbers must fit the single byte operand encoding
    assert length - 1 <= MAX_SINGLE_BYTE_SUBR
    subrs = [bytes([SUBR_0 + i, CALLSUBR, RETURN]) for i in range(1, length)]
    subrs.append(bytes([NUMBER_100, NUMBER_100, RMOVETO, RETURN]))
    return subrs


def test_local_subr_calling_itself() -> None:
    loop = bytes([SUBR_0, CALLSUBR])
    local_subr_index = [loop]
    parser = Type2CharStringParser("test")
    with pytest.raises(OSError):
        parser.parse(loop, [], local_subr_index, "test")


def test_global_subr_calling_itself() -> None:
    loop = bytes([SUBR_0, CALLGSUBR])
    global_subr_index = [loop]
    parser = Type2CharStringParser("test")
    with pytest.raises(OSError):
        parser.parse(loop, global_subr_index, None, "test")


def test_subrs_calling_each_other() -> None:
    first = bytes([SUBR_0 + 1, CALLSUBR])
    second = bytes([SUBR_0, CALLSUBR])
    local_subr_index = [first, second]
    parser = Type2CharStringParser("test")
    with pytest.raises(OSError):
        parser.parse(first, [], local_subr_index, "test")


def test_subrs_nested_up_to_limit() -> None:
    local_subr_index = _create_subr_chain(Type2CharStringParser.MAX_SUBR_NESTING)
    char_string = bytes([SUBR_0, CALLSUBR, ENDCHAR])
    sequence = Type2CharStringParser("test").parse(
        char_string, [], local_subr_index, "test"
    )
    assert sequence == [100, 100, COMMAND_RMOVETO, COMMAND_ENDCHAR]


def test_subrs_nested_beyond_limit() -> None:
    local_subr_index = _create_subr_chain(Type2CharStringParser.MAX_SUBR_NESTING + 1)
    char_string = bytes([SUBR_0, CALLSUBR, ENDCHAR])
    parser = Type2CharStringParser("test")
    with pytest.raises(OSError):
        parser.parse(char_string, [], local_subr_index, "test")
