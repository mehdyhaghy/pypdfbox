"""Fuzz / parity tests for CFF Top-DICT / Private-DICT operand+operator
decoding (wave 1575).

Targets ``CFFParser.read_integer_number`` / ``read_real_number`` /
``read_entry`` / ``read_operator`` / ``read_dict_data`` against the CFF
spec (Adobe Technical Note #5176, §4 Table 3 integer encodings and
Table 5 real-number nibble encodings) and upstream PDFBox 3.0.7
behaviour.

Each decoded value is asserted exactly. ``read_integer_number`` is
called with ``b0`` already consumed by the caller (matching upstream
``readEntry``), so the buffer passed to it holds only the *following*
bytes.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.dict_data import DictData


def _di(data: bytes) -> DataInputByteArray:
    return DataInputByteArray(data)


def _int(b0: int, tail: bytes = b"") -> int:
    return CFFParser.read_integer_number(_di(tail), b0)


def _real(body: bytes) -> float:
    # read_real_number assumes the 0x1e marker byte has been consumed.
    return CFFParser.read_real_number(_di(body))


# ---------------------------------------------------------------------------
# Integer operand encodings — CFF spec Table 3.
# ---------------------------------------------------------------------------


def test_single_byte_b0_139_is_zero() -> None:
    # b0 in 32..246 -> b0 - 139. 139 -> 0.
    assert _int(139) == 0


def test_single_byte_low_boundary_b0_32_is_minus_107() -> None:
    assert _int(32) == -107


def test_single_byte_high_boundary_b0_246_is_107() -> None:
    assert _int(246) == 107


@pytest.mark.parametrize(
    ("b0", "expected"),
    [(100, -39), (150, 11), (200, 61)],
    ids=["b0_100", "b0_150", "b0_200"],
)
def test_single_byte_sample_values(b0: int, expected: int) -> None:
    assert _int(b0) == expected


def test_two_byte_positive_min_is_108() -> None:
    # 247..250 form: (b0 - 247) * 256 + b1 + 108. b0=247,b1=0 -> 108.
    assert _int(247, b"\x00") == 108


def test_two_byte_positive_b1_nonzero() -> None:
    # b0=247, b1=0xff -> 0*256 + 255 + 108 = 363.
    assert _int(247, b"\xff") == 363


def test_two_byte_positive_max_is_1131() -> None:
    # b0=250, b1=255 -> 3*256 + 255 + 108 = 768 + 255 + 108 = 1131.
    assert _int(250, b"\xff") == 1131


def test_two_byte_negative_max_is_minus_108() -> None:
    # 251..254 form: -(b0 - 251) * 256 - b1 - 108. b0=251,b1=0 -> -108.
    assert _int(251, b"\x00") == -108


def test_two_byte_negative_b1_nonzero() -> None:
    # b0=251, b1=255 -> -0 - 255 - 108 = -363.
    assert _int(251, b"\xff") == -363


def test_two_byte_negative_min_is_minus_1131() -> None:
    # b0=254, b1=255 -> -3*256 - 255 - 108 = -768 - 255 - 108 = -1131.
    assert _int(254, b"\xff") == -1131


def test_positive_and_negative_two_byte_are_distinct_signs() -> None:
    # Same b1, adjacent ranges must yield opposite-sign magnitudes — a
    # 247-250 vs 251-254 sign mix-up would collapse these.
    pos = _int(247, b"\x10")
    neg = _int(251, b"\x10")
    assert pos > 0
    assert neg < 0


def test_shortint_28_positive() -> None:
    # b0=28 -> next two bytes, signed 16-bit big-endian. 0x0100 -> 256.
    assert _int(28, b"\x01\x00") == 256


def test_shortint_28_is_sign_extended_negative() -> None:
    # 0xFFFF as signed short -> -1 (not 65535). Catches missing sign-extend.
    assert _int(28, b"\xff\xff") == -1


def test_shortint_28_min_value() -> None:
    # 0x8000 -> -32768.
    assert _int(28, b"\x80\x00") == -32768


def test_shortint_28_max_value() -> None:
    # 0x7FFF -> 32767.
    assert _int(28, b"\x7f\xff") == 32767


def test_int32_29_positive() -> None:
    # b0=29 -> next four bytes, signed 32-bit big-endian.
    assert _int(29, b"\x00\x01\x00\x00") == 65536


def test_int32_29_is_sign_extended_negative() -> None:
    # 0xFFFFFFFF -> -1 (Java signed int), not 4294967295.
    assert _int(29, b"\xff\xff\xff\xff") == -1


def test_int32_29_min_value() -> None:
    # 0x80000000 -> -2147483648.
    assert _int(29, b"\x80\x00\x00\x00") == -2147483648


def test_int32_29_big_endian_byte_order() -> None:
    # 0x12345678 — wrong byte order would scramble this.
    assert _int(29, b"\x12\x34\x56\x78") == 0x12345678


# ---------------------------------------------------------------------------
# Real-number nibble decoder — CFF spec Table 5.
# ---------------------------------------------------------------------------


def test_real_simple_fraction_1_5() -> None:
    # 1 '.' 5 end -> nibbles 1,a,5,f -> 0x1a 0x5f.
    assert _real(b"\x1a\x5f") == 1.5


def test_real_negative_2_25() -> None:
    # 'e' 2 '.' 2 5 'f' -> -2.25. nibbles e,2,a,2,5,f.
    assert _real(b"\xe2\xa2\x5f") == -2.25


def test_real_minus_sign_nibble_e() -> None:
    # leading 'e' is the minus sign (NOT the terminator) -> -7.
    assert _real(b"\xe7\xff") == -7.0


def test_real_terminator_nibble_f_ends() -> None:
    # 4 2 'f' -> 42; the second nibble after f (here padding) is ignored.
    assert _real(b"\x42\xf0") == 42.0


def test_real_exponent_nibble_b_is_plus_e() -> None:
    # 1 'b' 1 0 'f' -> 1E10 = 1e10. nibbles 1,b,1,0,f.
    assert _real(b"\x1b\x10\xff") == 1e10


def test_real_exponent_nibble_c_is_minus_e() -> None:
    # 1 'c' 5 'f' -> 1E-5 = 1e-5. nibble c must be E- not E.
    assert _real(b"\x1c\x5f") == 1e-5


def test_real_nibble_c_distinct_from_nibble_b() -> None:
    # 'c' (E-) and 'b' (E) must produce different magnitudes for same digits.
    via_b = _real(b"\x2b\x3f")  # 2E3 = 2000
    via_c = _real(b"\x2c\x3f")  # 2E-3 = 0.002
    assert via_b == 2000.0
    assert via_c == 0.002
    assert via_b != via_c


def test_real_odd_nibble_count_with_terminator_high() -> None:
    # 3-digit number, terminator in the high nibble of the last byte.
    # 1 2 3 'f' -> 0x12 0x3f -> 123.
    assert _real(b"\x12\x3f") == 123.0


def test_real_even_nibble_count() -> None:
    # 9 9 9 9 'f' (terminator padded) -> 9999. nibbles 9,9,9,9,f,_.
    assert _real(b"\x99\x99\xf0") == 9999.0


def test_real_exponent_missing_appends_zero() -> None:
    # 5 'b' 'f' -> "5E" + appended "0" -> 5E0 -> 5.0 (exponent_missing path).
    assert _real(b"\x5b\xff") == 5.0


def test_real_repeated_exponent_marker_ignored() -> None:
    # 1 'b' 'b' 2 'f' -> second 'b' suppressed -> 1E2 -> 100.
    assert _real(b"\x1b\xb2\xff") == 100.0


def test_real_reserved_nibble_d_is_noop() -> None:
    # 'd' (0xD) is reserved -> upstream treats it as a no-op, not an error.
    # 1 'd' 2 'f' -> "12" -> 12.0.
    assert _real(b"\x1d\x2f") == 12.0


def test_real_empty_returns_zero() -> None:
    # Immediate terminator -> 0.0.
    assert _real(b"\xff") == 0.0


def test_real_pi_like_value_round_trips() -> None:
    # 3 '.' 1 4 1 5 'f' -> 3.1415.
    value = _real(b"\x3a\x14\x15\xff")
    assert math.isclose(value, 3.1415)


# ---------------------------------------------------------------------------
# Full entry / operator decoding through read_entry & read_dict_data.
# ---------------------------------------------------------------------------


def test_entry_single_operand_single_byte_operator() -> None:
    # operand 391 (encoded 0xf7 0x00 -> b0=247,b1=0 -> 108? no) ...
    # Use 139->0 then operator 'charset' (15).
    entry = CFFParser.read_entry(_di(b"\x8b\x0f"))  # 0x8b=139 -> 0, op 15
    assert entry.operands == [0]
    assert entry.operator_name == "charset"


def test_entry_multi_operand_operator() -> None:
    # FontBBox (operator 5) with 4 operands: 0 0 1000 1000.
    # 0 -> 139 (0x8b); 1000 = via 28-shortint 0x1c 0x03 0xe8.
    data = b"\x8b\x8b\x1c\x03\xe8\x1c\x03\xe8\x05"
    entry = CFFParser.read_entry(_di(data))
    assert entry.operands == [0, 0, 1000, 1000]
    assert entry.operator_name == "FontBBox"


def test_entry_two_byte_escape_operator() -> None:
    # FontMatrix is escape operator 12 7. Single operand 0 then 0x0c 0x07.
    entry = CFFParser.read_entry(_di(b"\x8b\x0c\x07"))
    assert entry.operator_name == "FontMatrix"


def test_entry_escape_operator_blue_scale() -> None:
    # BlueScale = 12 9. Real operand 0.039625 not needed; use int 0.
    entry = CFFParser.read_entry(_di(b"\x8b\x0c\x09"))
    assert entry.operator_name == "BlueScale"


def test_escape_key_offset_distinguishes_12_7_from_12_8() -> None:
    # FontMatrix (12 7) and StrokeWidth (12 8) must not collide — catches
    # an off-by-one in the (b1<<8|b0) escape key.
    fm = CFFParser.read_entry(_di(b"\x8b\x0c\x07")).operator_name
    sw = CFFParser.read_entry(_di(b"\x8b\x0c\x08")).operator_name
    assert fm == "FontMatrix"
    assert sw == "StrokeWidth"


def test_fontmatrix_array_operands_real_values() -> None:
    # /FontMatrix [0.001 0 0 0.001 0 0] with reals + 12 7.
    # 0.001 -> nibbles 0,'.',0,0,1,'f'? -> "0.001". Encode:
    #   0 'a' 0 0 1 'f' -> 0x0a 0x00 0x1f. Prefix 0x1e marker for real.
    real_001 = b"\x1e\x0a\x00\x1f"  # 1e marker, then 0.001
    zero = b"\x8b"  # 139 -> 0
    data = (
        real_001 + zero + zero + real_001 + zero + zero + b"\x0c\x07"
    )
    entry = CFFParser.read_entry(_di(data))
    assert entry.operator_name == "FontMatrix"
    assert len(entry.operands) == 6
    assert math.isclose(entry.operands[0], 0.001)
    assert entry.operands[1] == 0
    assert math.isclose(entry.operands[3], 0.001)


def test_dict_data_default_when_operator_absent() -> None:
    # Empty DICT -> get_number returns the supplied default.
    dict_ = DictData()
    assert dict_.get_number("charset", 0) == 0
    assert dict_.get_array("FontBBox", None) is None
    assert dict_.get_boolean("isFixedPitch", False) is False


def test_dict_data_round_trip_through_read_dict_data() -> None:
    # charset operand 391, then operator 15. 391 = 247-form:
    # (b0-247)*256 + b1 + 108 = 391 -> b0=247? 0*256 + b1 + 108 = 391 ->
    # b1 = 283 > 255, so use b0=248: 1*256 + b1 + 108 = 391 -> b1=27.
    # 0xf8 0x1b -> 248,27. Then operator 15 (charset).
    data = b"\xf8\x1b\x0f"
    dict_ = CFFParser.read_dict_data(_di(data))
    entry = dict_.get_entry("charset")
    assert entry is not None
    assert entry.get_number(0) == 391


def test_operand_with_no_operator_at_eof_is_dropped() -> None:
    # An operand stream that ends without an operator: read_dict_data over
    # a single 139-byte. read_entry would block on EOF, so feed via
    # read_dict_data with the trailing operator present, and separately
    # assert that an operator-less entry is dropped by DictData.add.
    dict_ = DictData()
    from pypdfbox.fontbox.cff.dict_data import Entry

    orphan = Entry()
    orphan.add_operand(5)  # no operator_name
    dict_.add(orphan)
    assert dict_.entries == {}


def test_operands_cleared_between_entries() -> None:
    # Two entries in one DICT: charset=0 then Encoding=1. Operand stacks
    # must not bleed across the operator boundary.
    data = b"\x8b\x0f\x8c\x10"  # 0 charset ; 1 Encoding
    dict_ = CFFParser.read_dict_data(_di(data))
    assert dict_.get_entry("charset").operands == [0]
    assert dict_.get_entry("Encoding").operands == [1]
