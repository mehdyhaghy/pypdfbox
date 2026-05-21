"""Wave 1368 — Type 2 charstring operator coverage: hint stems, masks,
subroutine bias formulas, and operand-byte dispatch.

Mirrors upstream ``Type2CharStringParser`` (CFF spec §4 + Adobe TN5177).
The Java parser must:

* track ``hstem`` / ``vstem`` operand counts for ``hintmask`` /
  ``cntrmask`` byte-length calculations;
* dispatch the three subroutine bias formulas (107 / 1131 / 32768)
  off the subroutine index size;
* decode the full Type 2 numeric operand encoding (1-byte tinyint,
  2-byte short, 5-byte fixed, ``shortint``).

These tests pin down those edges past the happy paths covered by
``test_type2_char_string_parser_coverage.py``.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type2_char_string_parser import Type2CharStringParser
from pypdfbox.fontbox.cff.type2_keyword import Type2KeyWord

# ---------- subroutine bias formula -----------------------------------


@pytest.mark.parametrize(
    ("subr_index_length", "operand", "expected"),
    [
        # Boundary at 1240 → bias 107.
        (0, 0, 107),
        (1, -1, 106),
        (1239, 1239, 1239 + 107),
        # Boundary at 33900 → bias 1131.
        (1240, 0, 1131),
        (1240, -1, 1130),
        (33899, 0, 1131),
        # Beyond 33900 → bias 32768.
        (33900, 0, 32768),
        (33900, -32768, 0),
        (50000, 1, 32769),
    ],
    ids=[
        "tiny_zero",
        "tiny_neg",
        "tiny_max",
        "medium_zero",
        "medium_neg",
        "medium_near_top",
        "large_zero",
        "large_neg_to_zero",
        "large_pos",
    ],
)
def test_calculate_subr_number_dispatch(
    subr_index_length: int, operand: int, expected: int
) -> None:
    assert (
        Type2CharStringParser.calculate_subr_number(operand, subr_index_length)
        == expected
    )


# ---------- mask byte-length formula ----------------------------------


@pytest.mark.parametrize(
    ("hstem_count", "vstem_count", "expected"),
    [
        (0, 0, 0),
        (1, 0, 1),
        (8, 0, 1),  # exactly 8 hints → 1 byte
        (9, 0, 2),  # 9 hints → 2 bytes
        (0, 8, 1),
        (8, 8, 2),
        (16, 1, 3),  # 17 hints → 3 bytes
        (100, 100, 25),  # 200 hints / 8 = 25 bytes
    ],
    ids=[
        "none",
        "one_h",
        "exactly_8_h",
        "nine_h",
        "exactly_8_v",
        "sixteen_total",
        "seventeen_total",
        "two_hundred_total",
    ],
)
def test_get_mask_length(
    hstem_count: int, vstem_count: int, expected: int
) -> None:
    assert (
        Type2CharStringParser.get_mask_length(hstem_count, vstem_count)
        == expected
    )


# ---------- count_numbers ---------------------------------------------


def test_count_numbers_counts_trailing_numbers_only() -> None:
    cmd = CharStringCommand.get_instance(1)  # HSTEM
    seq = [1, 2, cmd, 3, 4, 5]
    assert Type2CharStringParser.count_numbers(seq) == 3


def test_count_numbers_zero_when_last_is_command() -> None:
    cmd = CharStringCommand.get_instance(1)
    assert Type2CharStringParser.count_numbers([1, 2, 3, cmd]) == 0


def test_count_numbers_handles_floats() -> None:
    seq = [1, 2.5, 3]
    assert Type2CharStringParser.count_numbers(seq) == 3


def test_count_numbers_zero_on_empty_sequence() -> None:
    assert Type2CharStringParser.count_numbers([]) == 0


# ---------- read_number byte ranges -----------------------------------


def test_read_number_short_int_b0_28_signed_big_endian() -> None:
    parser = Type2CharStringParser("TestFont")
    # 0xFFFF as signed 16-bit big-endian = -1
    val, idx = parser.read_number(b"\xff\xff", 0, 28)
    assert val == -1
    assert idx == 2
    # 0x8000 as signed 16-bit = -32768
    val2, _ = parser.read_number(b"\x80\x00", 0, 28)
    assert val2 == -32768
    # 0x7FFF as signed 16-bit = 32767
    val3, _ = parser.read_number(b"\x7f\xff", 0, 28)
    assert val3 == 32767


def test_read_number_fixed_b0_255_decodes_signed_int_dot_fraction() -> None:
    parser = Type2CharStringParser("TestFont")
    # 0x00 0x01 0x80 0x00 → integer 1, fraction 0x8000/65535 ≈ 0.5
    val, idx = parser.read_number(b"\x00\x01\x80\x00", 0, 255)
    assert idx == 4
    assert val == pytest.approx(1.0 + 0x8000 / 65535.0, rel=1e-9)


def test_read_number_fixed_b0_255_negative_integer_part() -> None:
    parser = Type2CharStringParser("TestFont")
    # 0xFFFF (==-1) integer part, 0 fraction → -1.0
    val, _ = parser.read_number(b"\xff\xff\x00\x00", 0, 255)
    assert val == pytest.approx(-1.0)


def test_read_number_tiny_int_b0_32_returns_minus_107() -> None:
    parser = Type2CharStringParser("TestFont")
    val, idx = parser.read_number(b"", 0, 32)
    assert val == -107
    assert idx == 0


def test_read_number_tiny_int_b0_246_returns_107() -> None:
    parser = Type2CharStringParser("TestFont")
    val, idx = parser.read_number(b"", 0, 246)
    assert val == 107
    assert idx == 0


def test_read_number_two_byte_positive_boundary() -> None:
    parser = Type2CharStringParser("TestFont")
    # b0=247, b1=0 → 108. b0=250, b1=255 → 1131.
    assert parser.read_number(b"\x00", 0, 247) == (108, 1)
    assert parser.read_number(b"\xff", 0, 250) == (1131, 1)


def test_read_number_two_byte_negative_boundary() -> None:
    parser = Type2CharStringParser("TestFont")
    # b0=251, b1=0 → -108. b0=254, b1=255 → -1131.
    assert parser.read_number(b"\x00", 0, 251) == (-108, 1)
    assert parser.read_number(b"\xff", 0, 254) == (-1131, 1)


# ---------- hstem / vstem stacking via parse() -------------------------


def test_parse_tracks_hstem_count_via_hstem_command() -> None:
    # Operands: 100 (=-39+139? -> b0=100 means -39); use b0=200 (=61).
    # Build: push 4 numbers then HSTEM (1).
    # b0=200 → 200-139=61; encode four of them then operator 1.
    bytes_ = b"\xc8\xc8\xc8\xc8\x01"
    parser = Type2CharStringParser("TestFont")
    seq = parser.parse(bytes_, None, None, "")
    # 5 elements: 4 numbers + 1 command.
    assert len(seq) == 5
    assert seq[-1].get_type2_key_word() is Type2KeyWord.HSTEM


def test_parse_tracks_vstem_via_vstem_command_then_hintmask() -> None:
    # vstem (3) after 2 operands (1 v-stem pair), then hintmask (19)
    # with 1 byte of mask. Total hints = 1, so mask = 1 byte.
    # Numbers: 32 32 → -107, -107
    bytes_ = b"\x20\x20\x03\x13\xff"
    parser = Type2CharStringParser("TestFont")
    seq = parser.parse(bytes_, None, None, "")
    # Expected: [num, num, vstem_cmd, hintmask_cmd]
    assert len(seq) == 4
    assert seq[2].get_type2_key_word() is Type2KeyWord.VSTEM
    assert seq[3].get_type2_key_word() is Type2KeyWord.HINTMASK


def test_parse_cntrmask_advances_past_mask_bytes() -> None:
    # 1 hstem pair (2 operands + hstem op), then cntrmask (20) with 1
    # mask byte (hint count==1), then a single endchar (14).
    # numbers: -107 (32), 100 (=200-139=61 → byte 200)
    bytes_ = b"\x20\xc8\x01\x14\xff\x0e"
    parser = Type2CharStringParser("TestFont")
    seq = parser.parse(bytes_, None, None, "")
    # [num, num, hstem, cntrmask, endchar]
    assert len(seq) == 5
    assert seq[3].get_type2_key_word() is Type2KeyWord.CNTRMASK
    assert seq[4].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_parse_callgsubr_with_empty_global_index_is_noop() -> None:
    # callgsubr (b0=29) with no gsubrs → drops the operand, returns.
    bytes_ = b"\x20\x1d\x0e"  # push -107, callgsubr, endchar
    parser = Type2CharStringParser("TestFont")
    seq = parser.parse(bytes_, None, None, "")
    # The -107 is dropped by the no-op callgsubr (it pre-pops nothing
    # when gsi is empty) — actually, when gsi is empty, the parser
    # short-circuits before popping. Verify by checking sequence ends
    # with the endchar command.
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_parse_callgsubr_with_supplied_subrs_inlines_them() -> None:
    # GSubr 0 body: just push 100 (b0=200 → 61) and return (b0=11).
    # Calling charstring: push subr-number=0 (after bias 107 → operand
    # must be -107 == 32). 1 entry subr index → bias 107.
    # operand -107 with bias 107 → subr index 0.
    gsi = [b"\xc8\x0b"]  # push 61, ret
    parser = Type2CharStringParser("TestFont")
    bytes_ = b"\x20\x1d\x0e"  # push -107, callgsubr, endchar
    seq = parser.parse(bytes_, gsi, None, "")
    # After inlining: push 61 from gsubr (ret is stripped), then endchar.
    assert 61 in seq
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_parse_hintmask_mask_byte_count_scales_with_hint_count() -> None:
    # 9 hstem pairs (18 operands + hstem op) → 9 hstems. With 0 vstems
    # the parser then resets vstem_count from count_numbers // 2 = 0
    # at hintmask; hint_count = 9, mask = ceil(9/8) = 2 bytes.
    # Each operand: byte 200 → 61.
    parser = Type2CharStringParser("TestFont")
    body = b"\xc8" * 18 + b"\x01" + b"\x13" + b"\xff\xff" + b"\x0e"
    seq = parser.parse(body, None, None, "")
    # Verify endchar is reached without ValueError.
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR
