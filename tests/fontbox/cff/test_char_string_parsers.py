"""Hand-written tests for the Type 1 / Type 2 char-string byte parsers."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff import (
    CharStringCommand,
    Type1CharStringParser,
    Type1KeyWord,
    Type2CharStringParser,
    Type2KeyWord,
)
from pypdfbox.fontbox.cff.type2_char_string_parser import _GlyphData

# ---------- Type 1 -----------------------------------------------------------

def _enc_t1_int(n: int) -> bytes:
    """Encode a Type 1 integer per Adobe Type 1 §6.2."""
    if -107 <= n <= 107:
        return bytes([n + 139])
    if 108 <= n <= 1131:
        v = n - 108
        return bytes([(v >> 8) + 247, v & 0xFF])
    if -1131 <= n <= -108:
        v = -n - 108
        return bytes([(v >> 8) + 251, v & 0xFF])
    return bytes([255]) + n.to_bytes(4, "big", signed=True)


def test_type1_parse_simple_command() -> None:
    # Push 100 then HSBW (op 13).
    data = _enc_t1_int(100) + bytes([13])
    parser = Type1CharStringParser("Test")
    seq = parser.parse(data, [], "glyph")
    assert seq[0] == 100
    assert isinstance(seq[1], CharStringCommand)
    assert seq[1].get_type1_key_word() is Type1KeyWord.HSBW


def test_type1_parse_two_byte_command() -> None:
    # Push 1, push 2, then DIV (12 12).
    data = _enc_t1_int(1) + _enc_t1_int(2) + bytes([12, 12])
    parser = Type1CharStringParser("Test")
    seq = parser.parse(data, [], "glyph")
    assert seq[0] == 1
    assert seq[1] == 2
    assert seq[2].get_type1_key_word() is Type1KeyWord.DIV


def test_type1_parse_negative_int() -> None:
    data = _enc_t1_int(-50) + bytes([5])  # rlineto
    parser = Type1CharStringParser("Test")
    seq = parser.parse(data, [], "glyph")
    assert seq[0] == -50


def test_type1_parse_32bit_int() -> None:
    big = 100_000
    data = _enc_t1_int(big) + bytes([5])
    parser = Type1CharStringParser("Test")
    seq = parser.parse(data, [], "glyph")
    assert seq[0] == big


def test_type1_parse_callsubr_inlines_subr() -> None:
    # subr[0] = "5 hlineto" (push 5, op 6).
    subr = _enc_t1_int(5) + bytes([6])
    # main: callsubr 0
    main = _enc_t1_int(0) + bytes([10])
    parser = Type1CharStringParser("Test")
    seq = parser.parse(main, [subr], "glyph")
    assert seq[0] == 5
    assert seq[1].get_type1_key_word() is Type1KeyWord.HLINETO


def test_type1_parse_callsubr_strips_return() -> None:
    # subr ending in RET (op 11) — RET must be stripped after inlining.
    subr = _enc_t1_int(7) + bytes([6, 11])
    main = _enc_t1_int(0) + bytes([10])
    parser = Type1CharStringParser("Test")
    seq = parser.parse(main, [subr], "glyph")
    assert seq[-1].get_type1_key_word() is Type1KeyWord.HLINETO  # not RET


# ---------- Type 2 -----------------------------------------------------------

def _enc_t2_int(n: int) -> bytes:
    """Encode a Type 2 integer per Adobe Tech Note 5177 §3.1."""
    if -107 <= n <= 107:
        return bytes([n + 139])
    if 108 <= n <= 1131:
        v = n - 108
        return bytes([(v >> 8) + 247, v & 0xFF])
    if -1131 <= n <= -108:
        v = -n - 108
        return bytes([(v >> 8) + 251, v & 0xFF])
    if -32768 <= n <= 32767:
        return bytes([28]) + n.to_bytes(2, "big", signed=True)
    raise ValueError(n)


def test_type2_parse_simple_command() -> None:
    data = _enc_t2_int(50) + _enc_t2_int(60) + bytes([21])  # rmoveto
    parser = Type2CharStringParser("Test")
    seq = parser.parse(data, None, None, "glyph")
    assert seq[0] == 50
    assert seq[1] == 60
    assert isinstance(seq[2], CharStringCommand)
    assert seq[2].get_type2_key_word() is Type2KeyWord.RMOVETO


def test_type2_parse_short_int() -> None:
    # 28 introduces a signed 16-bit short.
    data = bytes([28, 0xFF, 0x00]) + bytes([21])  # -256 then rmoveto
    parser = Type2CharStringParser("Test")
    seq = parser.parse(data, None, None, "glyph")
    assert seq[0] == -256


def test_type2_parse_endchar() -> None:
    data = bytes([14])
    parser = Type2CharStringParser("Test")
    seq = parser.parse(data, None, None, "glyph")
    assert seq[0].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_type2_parse_hintmask_skips_mask_bytes() -> None:
    # 4 vstem hints + 4 hstem hints → 1 mask byte after hintmask.
    # Build: (4 numbers) hstem (4 numbers) vstem (some numbers ignored)
    # then hintmask + 1 byte mask + endchar.
    body = b""
    for n in (1, 2, 3, 4):
        body += _enc_t2_int(n)
    body += bytes([1])  # hstem (counts 2 pairs → hstem_count = 2)
    for n in (5, 6, 7, 8):
        body += _enc_t2_int(n)
    body += bytes([3])  # vstem (counts 2 pairs → vstem_count = 2)
    body += bytes([19, 0xFF])  # hintmask + 1 mask byte (4 hints / 8 = 1)
    body += bytes([14])  # endchar
    parser = Type2CharStringParser("Test")
    seq = parser.parse(body, None, None, "glyph")
    # Last token must be ENDCHAR — if mask skip was wrong we'd parse 0xFF as op.
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_type2_parse_invalid_truncated_two_byte() -> None:
    parser = Type2CharStringParser("Test")
    with pytest.raises(ValueError):
        parser.parse(bytes([12]), None, None, "glyph")


# ---------- Type 1 method-level tests ---------------------------------------

def test_type1_read_number_single_byte() -> None:
    parser = Type1CharStringParser("Test")
    # b0 = 139 -> 0
    value, new_i = parser.read_number(bytes([139]), 1, 139)
    assert value == 0
    assert new_i == 1


def test_type1_read_number_two_byte_positive() -> None:
    parser = Type1CharStringParser("Test")
    # b0=247, b1=0 -> 108
    value, new_i = parser.read_number(bytes([247, 0]), 1, 247)
    assert value == 108
    assert new_i == 2


def test_type1_read_number_two_byte_negative() -> None:
    parser = Type1CharStringParser("Test")
    value, new_i = parser.read_number(bytes([251, 0]), 1, 251)
    assert value == -108
    assert new_i == 2


def test_type1_read_number_32bit() -> None:
    parser = Type1CharStringParser("Test")
    raw = bytes([255]) + (123_456).to_bytes(4, "big", signed=True)
    value, new_i = parser.read_number(raw, 1, 255)
    assert value == 123_456
    assert new_i == 5


def test_type1_read_number_32bit_truncated() -> None:
    parser = Type1CharStringParser("Test")
    with pytest.raises(ValueError):
        parser.read_number(bytes([255, 0, 0]), 1, 255)


def test_type1_read_command_one_byte() -> None:
    parser = Type1CharStringParser("Test")
    cmd, new_i = parser.read_command(bytes([13]), 1, 13)
    assert cmd.get_type1_key_word() is Type1KeyWord.HSBW
    assert new_i == 1


def test_type1_read_command_two_byte() -> None:
    parser = Type1CharStringParser("Test")
    cmd, new_i = parser.read_command(bytes([12, 12]), 1, 12)
    assert cmd.get_type1_key_word() is Type1KeyWord.DIV
    assert new_i == 2


def test_type1_read_command_two_byte_truncated() -> None:
    parser = Type1CharStringParser("Test")
    with pytest.raises(ValueError):
        parser.read_command(bytes([12]), 1, 12)


def test_type1_remove_integer_returns_int() -> None:
    seq: list = [1, 2, 5]
    assert Type1CharStringParser.remove_integer(seq) == 5
    assert seq == [1, 2]


def test_type1_remove_integer_handles_div() -> None:
    div_cmd = CharStringCommand.get_instance(12, 12)
    seq: list = [10, 2, div_cmd]
    # b=10, a=2 -> 10 // 2 == 5
    assert Type1CharStringParser.remove_integer(seq) == 5


def test_type1_remove_integer_empty_raises() -> None:
    with pytest.raises(OSError):
        Type1CharStringParser.remove_integer([])


def test_type1_process_call_subr_skips_non_int_operand() -> None:
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    cmd = CharStringCommand.get_instance(13)
    seq: list = [cmd]
    parser.process_call_subr([], seq)
    assert seq == []


def test_type1_process_call_other_subr_begin_flex() -> None:
    parser = Type1CharStringParser("Test")
    parser._current_glyph = "g"
    # othersubr 1 (begin flex), num_args=0
    seq: list = [0, 1]
    # data: [16] CALLOTHERSUBR byte at i=0; we pass i=0
    new_i = parser.process_call_other_subr(bytes([16]), 0, seq)
    assert new_i == 1
    assert seq[-2] == 1
    assert seq[-1] is CharStringCommand.COMMAND_CALLOTHERSUBR


# ---------- Type 2 method-level tests ---------------------------------------

def test_type2_calculate_subr_number_small() -> None:
    assert Type2CharStringParser.calculate_subr_number(0, 100) == 107
    assert Type2CharStringParser.calculate_subr_number(-107, 100) == 0


def test_type2_calculate_subr_number_medium() -> None:
    assert Type2CharStringParser.calculate_subr_number(0, 2000) == 1131


def test_type2_calculate_subr_number_large() -> None:
    assert Type2CharStringParser.calculate_subr_number(0, 40000) == 32768


def test_type2_get_mask_length_zero_hints() -> None:
    assert Type2CharStringParser.get_mask_length(0, 0) == 0


def test_type2_get_mask_length_round_up() -> None:
    # 1 hint -> 1 byte
    assert Type2CharStringParser.get_mask_length(1, 0) == 1
    # 8 hints -> 1 byte
    assert Type2CharStringParser.get_mask_length(4, 4) == 1
    # 9 hints -> 2 bytes
    assert Type2CharStringParser.get_mask_length(5, 4) == 2


def test_type2_count_numbers_trailing_operands() -> None:
    seq: list = [1, 2, CharStringCommand.get_instance(14), 3, 4, 5]
    assert Type2CharStringParser.count_numbers(seq) == 3


def test_type2_count_numbers_floats_count() -> None:
    seq: list = [1, 2.5, 3]
    assert Type2CharStringParser.count_numbers(seq) == 3


def test_type2_count_numbers_no_trailing() -> None:
    seq: list = [CharStringCommand.get_instance(14)]
    assert Type2CharStringParser.count_numbers(seq) == 0


def test_type2_read_number_short() -> None:
    parser = Type2CharStringParser("Test")
    value, new_i = parser.read_number(bytes([28, 0xFF, 0x00]), 1, 28)
    assert value == -256
    assert new_i == 3


def test_type2_read_number_short_truncated() -> None:
    parser = Type2CharStringParser("Test")
    with pytest.raises(ValueError):
        parser.read_number(bytes([28, 0]), 1, 28)


def test_type2_read_number_fixed() -> None:
    parser = Type2CharStringParser("Test")
    raw = bytes([255, 0x00, 0x01, 0x80, 0x00])
    value, new_i = parser.read_number(raw, 1, 255)
    # 1 + 0x8000/65535
    assert abs(value - (1 + 0x8000 / 65535.0)) < 1e-9
    assert new_i == 5


def test_type2_read_command_hstem_updates_hstem_count() -> None:
    parser = Type2CharStringParser("Test")
    gd = _GlyphData(sequence=[1, 2, 3, 4])
    cmd, new_i = parser.read_command(bytes([1]), 1, 1, gd)
    assert cmd.get_type2_key_word() is Type2KeyWord.HSTEM
    assert gd.hstem_count == 2  # 4 numbers / 2


def test_type2_read_command_vstem_updates_vstem_count() -> None:
    parser = Type2CharStringParser("Test")
    gd = _GlyphData(sequence=[1, 2])
    cmd, new_i = parser.read_command(bytes([3]), 1, 3, gd)
    assert cmd.get_type2_key_word() is Type2KeyWord.VSTEM
    assert gd.vstem_count == 1


def test_type2_read_command_two_byte() -> None:
    parser = Type2CharStringParser("Test")
    gd = _GlyphData()
    cmd, new_i = parser.read_command(bytes([12, 35]), 1, 12, gd)
    assert isinstance(cmd, CharStringCommand)
    assert new_i == 2


def test_type2_read_command_two_byte_truncated() -> None:
    parser = Type2CharStringParser("Test")
    gd = _GlyphData()
    with pytest.raises(ValueError):
        parser.read_command(bytes([12]), 1, 12, gd)


def test_type2_get_subr_bytes_returns_indexed_subr() -> None:
    parser = Type2CharStringParser("Test")
    subrs = [b"\x0e"] * 10  # 10 subrs (small index)
    gd = _GlyphData(sequence=[-107])  # 107 + (-107) = 0
    result = parser.get_subr_bytes(subrs, gd)
    assert result == b"\x0e"


def test_type2_get_subr_bytes_out_of_range_returns_none() -> None:
    parser = Type2CharStringParser("Test")
    subrs: list[bytes] = [b"\x0e"]
    gd = _GlyphData(sequence=[100])  # 107 + 100 = 207, > 1
    assert parser.get_subr_bytes(subrs, gd) is None


def test_type2_get_subr_bytes_empty_sequence_returns_none() -> None:
    parser = Type2CharStringParser("Test")
    gd = _GlyphData()
    assert parser.get_subr_bytes([b"\x0e"], gd) is None


def test_type2_process_call_subr_with_local_index() -> None:
    parser = Type2CharStringParser("Test")
    # Local subr 0 ("107 + (-107) = 0") containing endchar (op 14).
    subr = bytes([14])
    gd = _GlyphData(sequence=[-107])
    parser.process_call_subr([], [subr], gd)
    # endchar appended (RET strip only fires on RET)
    assert gd.sequence
    assert gd.sequence[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_type2_process_call_g_subr_with_global_index() -> None:
    parser = Type2CharStringParser("Test")
    subr = bytes([14])
    gd = _GlyphData(sequence=[-107])
    parser.process_call_g_subr([subr], [], gd)
    assert gd.sequence[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_type2_process_subr_strips_trailing_ret() -> None:
    parser = Type2CharStringParser("Test")
    # Subr ending in RET (op 11): should be stripped.
    subr = bytes([14, 11])
    gd = _GlyphData()
    parser.process_subr([], [], subr, gd)
    # ENDCHAR remains, RET stripped
    assert len(gd.sequence) == 1
    assert gd.sequence[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_type2_parse_sequence_populates_glyph_data() -> None:
    parser = Type2CharStringParser("Test")
    gd = _GlyphData()
    # Push 50, 60, then rmoveto (21).
    data = _enc_t2_int(50) + _enc_t2_int(60) + bytes([21])
    parser.parse_sequence(data, [], [], gd)
    assert gd.sequence[0] == 50
    assert gd.sequence[1] == 60
    assert gd.sequence[2].get_type2_key_word() is Type2KeyWord.RMOVETO


def test_type2_str_returns_font_name() -> None:
    assert str(Type2CharStringParser("MyFont")) == "MyFont"


def test_type2_to_string_returns_font_name() -> None:
    assert Type2CharStringParser("MyFont").to_string() == "MyFont"
