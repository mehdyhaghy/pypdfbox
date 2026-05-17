"""Coverage-boost tests for
:mod:`pypdfbox.fontbox.cff.type1_char_string_parser`.

These tests target the still-uncovered branches in the Type 1 char-
string parser: the CALLOTHERSUBR family (othersubr 0 / 3 / N + pop
loop), the CALLSUBR safety paths (empty sequence, non-int operand,
out-of-range index), ``remove_integer`` DIV handling, and the
operand-byte truncation guards in ``read_number``.

Each test name corresponds to the upstream branch being exercised so a
coverage regression bisect maps straight back to the source operation.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type1_char_string_parser import (
    Type1CharStringParser,
)
from pypdfbox.fontbox.cff.type1_keyword import Type1KeyWord

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _enc_int(n: int) -> bytes:
    """Encode an integer per Adobe Type 1 spec section 6.2."""
    if -107 <= n <= 107:
        return bytes([n + 139])
    if 108 <= n <= 1131:
        v = n - 108
        return bytes([(v >> 8) + 247, v & 0xFF])
    if -1131 <= n <= -108:
        v = -n - 108
        return bytes([(v >> 8) + 251, v & 0xFF])
    return bytes([255]) + n.to_bytes(4, "big", signed=True)


# ---------------------------------------------------------------------
# process_call_subr — empty sequence + non-int operand + out-of-range
# operand (lines 96-97, 99-105, 117-124).
# ---------------------------------------------------------------------


def test_process_call_subr_empty_sequence_is_noop() -> None:
    """``processCallSubr`` with an empty stack must simply return
    without raising (line 96-97)."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    seq: list = []
    parser.process_call_subr([b"\x0e"], seq)
    assert seq == []


def test_process_call_subr_out_of_range_drops_trailing_ints(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An operand outside ``[0, len(subrs))`` must log a warning and
    pop the trailing integer operands off the stack (lines 117-124)."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    # Stack: 10, 20, 30, 999 (operand). subrs only has 1 entry → 999 OOR.
    seq: list = [10, 20, 30, 999]
    with caplog.at_level("WARNING"):
        parser.process_call_subr([b"\x0e"], seq)
    # Trailing ints stripped.
    assert seq == []
    assert any("CALLSUBR is ignored" in r.message for r in caplog.records)


def test_process_call_subr_out_of_range_stops_at_non_int() -> None:
    """The post-warning pop loop terminates at the first non-int (no
    state leak past command tokens)."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    sentinel = CharStringCommand.get_instance(13)  # HSBW
    seq: list = [sentinel, 1, 2, 999]
    parser.process_call_subr([], seq)
    # Sentinel survives; ints (and the 999 operand) gone.
    assert seq == [sentinel]


def test_process_call_subr_negative_operand_treated_as_out_of_range() -> None:
    """A negative operand satisfies ``< len(subrs)`` only if non-negative
    too; ``0 <= operand`` fails so the OOR branch fires."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    seq: list = [5, -1]
    parser.process_call_subr([b"\x0e"], seq)
    assert seq == []


# ---------------------------------------------------------------------
# process_call_other_subr — early returns + each othersubr-num branch
# (lines 137, 141, 146-151, 156-161, 170-172, 174-178).
# ---------------------------------------------------------------------


def test_process_call_other_subr_short_stack_returns_cursor() -> None:
    """Fewer than 2 operands on the stack → early return (line 137)."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    seq: list = [42]  # only 1 element
    new_i = parser.process_call_other_subr(bytes([16, 0]), 0, seq)
    # Cursor advanced past CALLOTHERSUBR (the +1 on line 135).
    assert new_i == 1
    # Stack untouched.
    assert seq == [42]


def test_process_call_other_subr_non_int_operands_return_cursor() -> None:
    """If either of the two popped values isn't an int the parser must
    return without touching the stack (line 140-141)."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    cmd = CharStringCommand.get_instance(13)
    seq: list = [cmd, cmd]
    new_i = parser.process_call_other_subr(bytes([16, 0]), 0, seq)
    assert new_i == 1


def test_process_call_other_subr_end_flex_pops_three_values() -> None:
    """othersubr_num == 0 (end flex): pops 2 ints + drops one extra +
    appends ``0`` + ``COMMAND_CALLOTHERSUBR`` (lines 144-151)."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    # Stack layout (top-of-stack last): extra=99, y=20, x=10, num_args=3, othersubr=0
    seq: list = [99, 20, 10, 3, 0]
    new_i = parser.process_call_other_subr(bytes([16]), 0, seq)
    assert new_i == 1
    # End-flex appends 0 + COMMAND_CALLOTHERSUBR (the extra was popped).
    # The stack-leftover warning fires because results still holds 2 ints.
    assert seq[-1] is CharStringCommand.COMMAND_CALLOTHERSUBR
    assert seq[-2] == 0


def test_process_call_other_subr_hint_replacement_pops_one(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """othersubr_num == 3 (hint replacement): pop a single integer
    (lines 156-158). With no trailing pop, the warning at line 174-178
    fires."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    seq: list = [77, 1, 3]
    with caplog.at_level("WARNING"):
        new_i = parser.process_call_other_subr(bytes([16]), 0, seq)
    assert new_i == 1
    assert any("PostScript stack" in r.message for r in caplog.records)


def test_process_call_other_subr_default_branch_pops_num_args() -> None:
    """othersubr_num >= 2 and != 3 → pop ``num_args`` integers
    (lines 159-161)."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    # Stack: x, y, z, num_args=3, othersubr=5
    seq: list = [1, 2, 3, 3, 5]
    new_i = parser.process_call_other_subr(bytes([16]), 0, seq)
    assert new_i == 1


def test_process_call_other_subr_consumes_trailing_pop_pair() -> None:
    """Trailing ``12 17`` (POP) pairs must consume both bytes and push
    one ``result`` back onto the stack (lines 165-172)."""
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    seq: list = [1, 1, 3]  # results from othersubr 3 (1 int popped)
    # Bytes: CALLOTHERSUBR (16) at index 0, then 12 17 (POP) at 1-2.
    data = bytes([16, 12, 17])
    new_i = parser.process_call_other_subr(data, 0, seq)
    assert new_i == 3  # consumed CALLOTHERSUBR + 2-byte POP
    # The popped result (1) was pushed back onto the stack.
    assert seq[-1] == 1


# ---------------------------------------------------------------------
# remove_integer — DIV expansion + error paths (lines 195-204).
# ---------------------------------------------------------------------


def test_remove_integer_div_with_insufficient_operands_raises() -> None:
    """DIV with fewer than 2 operands below it raises OSError (line
    194-196)."""
    div_cmd = CharStringCommand.get_instance(12, 12)
    seq: list = [div_cmd]  # only the DIV command, no operands below
    with pytest.raises(OSError, match="DIV with insufficient"):
        Type1CharStringParser.remove_integer(seq)


def test_remove_integer_div_with_non_int_operands_raises() -> None:
    """DIV operands must be ints — non-int triggers OSError (line
    199-201)."""
    div_cmd = CharStringCommand.get_instance(12, 12)
    seq: list = ["junk", 2, div_cmd]
    with pytest.raises(OSError, match="DIV operands are not integers"):
        Type1CharStringParser.remove_integer(seq)


def test_remove_integer_rejects_non_int_non_div_command() -> None:
    """A non-DIV command on top of the stack raises OSError (line
    203-204)."""
    hsbw_cmd = CharStringCommand.get_instance(13)  # HSBW, not DIV
    seq: list = [hsbw_cmd]
    with pytest.raises(OSError, match="Unexpected char string command"):
        Type1CharStringParser.remove_integer(seq)


# ---------------------------------------------------------------------
# read_number — truncation guards (lines 227-228, 233-234, 243-244).
# ---------------------------------------------------------------------


def test_read_number_two_byte_positive_truncated_raises() -> None:
    """247-250 needs a follow-up byte; missing → ValueError (line
    227-228)."""
    parser = Type1CharStringParser("Test")
    with pytest.raises(ValueError, match="Truncated"):
        # b0=247, no following byte.
        parser.read_number(bytes([247]), 1, 247)


def test_read_number_two_byte_negative_truncated_raises() -> None:
    """251-254 needs a follow-up byte; missing → ValueError (line
    233-234)."""
    parser = Type1CharStringParser("Test")
    with pytest.raises(ValueError, match="Truncated"):
        parser.read_number(bytes([251]), 1, 251)


def test_read_number_rejects_invalid_b0() -> None:
    """A b0 outside the documented operand ranges raises ValueError
    (lines 243-244)."""
    parser = Type1CharStringParser("Test")
    with pytest.raises(ValueError, match="Invalid Type 1 operand"):
        parser.read_number(bytes([5]), 0, 5)  # 5 is an operator byte, not number


# ---------------------------------------------------------------------
# End-to-end smoke through ``parse`` — exercises the inner ``_parse``
# CALLOTHERSUBR dispatch line 77.
# ---------------------------------------------------------------------


def test_parse_dispatches_callothersubr_through_byte_stream() -> None:
    """Hand a full byte stream containing ``12 16`` (CALLOTHERSUBR) and
    verify the inner ``_parse`` loop routes through
    ``process_call_other_subr`` (line 77)."""
    parser = Type1CharStringParser("Test")
    # Stack: push 1 (begin-flex num_args), push 1 (othersubr), then 12 16.
    data = _enc_int(1) + _enc_int(1) + bytes([12, 16, 14])  # 14 = endchar
    seq = parser.parse(data, [], "g")
    # Begin-flex pushed 1 + COMMAND_CALLOTHERSUBR; endchar appended after.
    assert CharStringCommand.COMMAND_CALLOTHERSUBR in seq


def test_parse_strips_return_from_subr_top_of_stack() -> None:
    """After a CALLSUBR inlines a subr whose last token is RET, the RET
    must be stripped (line 110-116). This exercises the
    ``Type1KeyWord.RET`` branch that the existing tests cover only
    indirectly."""
    parser = Type1CharStringParser("Test")
    # subr[0]: push 9, op 5 (rlineto), then RET (op 11).
    subr = _enc_int(9) + bytes([5, 11])
    # main: 0 callsubr.
    main = _enc_int(0) + bytes([10])
    seq = parser.parse(main, [subr], "g")
    assert seq[-1].get_type1_key_word() is Type1KeyWord.RLINETO


# ---------------------------------------------------------------------
# Smoke for the bare-parse branch (no current glyph).
# ---------------------------------------------------------------------


def test_parse_records_current_glyph_attribute() -> None:
    """``parse`` must set ``_current_glyph`` (used by warning logs)."""
    parser = Type1CharStringParser("MyFont")
    parser.parse(bytes([14]), [], "MyGlyph")
    assert parser._current_glyph == "MyGlyph"
