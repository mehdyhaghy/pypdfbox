"""Wave 1368 — Top / Private DICT operand stack edge cases.

Exercises the CFF DICT integer / real-number encodings (CFF spec
Table 3, Table 4) past the happy paths covered by
``test_cff_parser_coverage*.py``. Focuses on:

* The 1-byte ``b0`` ranges (32-246, 247-250, 251-254) and their
  boundary numbers.
* The 2-byte short (``b0 == 28``) and 4-byte int (``b0 == 29``)
  paths, including negative values.
* The 5-byte real-number BCD stream (``b0 == 30``), including the
  ``E`` / ``E-`` exponent markers and signed exponents.
* Multi-operand stacking: a DICT entry can carry many operands before
  the operator byte.
* ``Entry.get_delta`` running-sum semantics on negative deltas and a
  single-element list.
* ``DictData.add`` silently dropping operator-less entries (mirrors
  upstream ``CFFParser.java`` line 1316).
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.data_input_byte_array import DataInputByteArray
from pypdfbox.fontbox.cff.dict_data import DictData, Entry


def test_read_integer_number_boundary_b0_32_returns_minus_107() -> None:
    # b0 == 32 → 32 - 139 = -107 (lowest of the 1-byte range)
    inp = DataInputByteArray(b"\x20")
    assert CFFParser.read_integer_number(inp, 0x20) == -107


def test_read_integer_number_boundary_b0_246_returns_107() -> None:
    # b0 == 246 → 246 - 139 = 107 (highest of the 1-byte range)
    inp = DataInputByteArray(b"\xf6")
    assert CFFParser.read_integer_number(inp, 0xF6) == 107


def test_read_integer_number_positive_two_byte_min_108() -> None:
    # b0 == 247, b1 == 0 → (247-247)*256 + 0 + 108 = 108
    inp = DataInputByteArray(b"\x00")
    assert CFFParser.read_integer_number(inp, 247) == 108


def test_read_integer_number_positive_two_byte_max_1131() -> None:
    # b0 == 250, b1 == 255 → (250-247)*256 + 255 + 108 = 1131
    inp = DataInputByteArray(b"\xff")
    assert CFFParser.read_integer_number(inp, 250) == 1131


def test_read_integer_number_negative_two_byte_min_minus_108() -> None:
    # b0 == 251, b1 == 0 → -(251-251)*256 - 0 - 108 = -108
    inp = DataInputByteArray(b"\x00")
    assert CFFParser.read_integer_number(inp, 251) == -108


def test_read_integer_number_negative_two_byte_max_minus_1131() -> None:
    # b0 == 254, b1 == 255 → -(254-251)*256 - 255 - 108 = -1131
    inp = DataInputByteArray(b"\xff")
    assert CFFParser.read_integer_number(inp, 254) == -1131


def test_read_integer_number_short_negative_extreme() -> None:
    # b0 == 28, 2-byte big-endian signed short, -32768 minimum.
    inp = DataInputByteArray(b"\x80\x00")
    assert CFFParser.read_integer_number(inp, 28) == -32768


def test_read_integer_number_int_negative() -> None:
    # b0 == 29, 4-byte big-endian signed int.
    inp = DataInputByteArray(b"\xff\xff\xff\xff")
    assert CFFParser.read_integer_number(inp, 29) == -1


def test_read_integer_number_int_max_value() -> None:
    # 0x7fffffff = 2147483647 (Java Integer.MAX_VALUE)
    inp = DataInputByteArray(b"\x7f\xff\xff\xff")
    assert CFFParser.read_integer_number(inp, 29) == 2147483647


def test_read_real_number_negative_exponent_signed() -> None:
    # BCD encoding for "-1.5E-2": nibbles 0xE 0x1 0xA 0x5 0xC 0x2 0xF
    # bytes: 0xE1 0xA5 0xC2 0xFF
    inp = DataInputByteArray(b"\xe1\xa5\xc2\xff")
    assert CFFParser.read_real_number(inp) == pytest.approx(-1.5e-2)


def test_read_real_number_exponent_without_mantissa_digit() -> None:
    # BCD "1E": nibbles 0x1 0xB 0xF -> bytes 0x1B 0xFx. The lone "E"
    # is followed immediately by terminator → upstream appends a
    # trailing "0" so the float parser sees "1E0".
    inp = DataInputByteArray(b"\x1b\xf0")
    assert CFFParser.read_real_number(inp) == pytest.approx(1.0)


def test_read_real_number_pure_decimal() -> None:
    # BCD ".25": nibbles 0xA 0x2 0x5 0xF -> bytes 0xA2 0x5F
    inp = DataInputByteArray(b"\xa2\x5f")
    assert CFFParser.read_real_number(inp) == pytest.approx(0.25)


def test_read_entry_stacks_multiple_operands_then_operator() -> None:
    # /FontBBox is operator 5; build a DICT entry with four operands.
    # Operands: -100 (255 byte sequence 251,148), 0, 1000 (two-byte
    # 247-250 form: 250,32 → (250-247)*256+32+108 = 908+...) — use
    # the simple single-byte form for clarity.
    # Build: 32 (=-107), 100 (=−39+...) → -39
    # Use single-byte operands in [32,246]:
    #   0x77 → 119-139=-20
    #   0x7B → 123-139=-16
    #   0x95 → 149-139=10
    #   0xAA → 170-139=31
    # then operator 5 = /FontBBox
    inp = DataInputByteArray(b"\x77\x7b\x95\xaa\x05")
    entry = CFFParser.read_entry(inp)
    assert entry.operator_name == "FontBBox"
    assert entry.get_operands() == [-20, -16, 10, 31]


def test_read_entry_int_b0_29_signed_mid_value() -> None:
    # /UniqueID-style operator with a 4-byte signed int operand.
    # 0x00010203 = 66051. operator 13 = /UniqueID.
    inp = DataInputByteArray(b"\x1d\x00\x01\x02\x03\x0d")
    entry = CFFParser.read_entry(inp)
    assert entry.operator_name == "UniqueID"
    assert entry.get_operands() == [66051]


def test_dictdata_add_drops_entry_without_operator() -> None:
    # An entry whose operator_name is None must not appear in the map.
    d = DictData()
    orphan = Entry()
    orphan.add_operand(42)
    d.add(orphan)
    assert d.get_entry("anything") is None
    assert d.entries == {}


def test_entry_get_delta_negative_running_sum() -> None:
    # /BlueValues "[-50 75 -25 100]" → delta-decoded:
    #   -50, -50+75=25, 25-25=0, 0+100=100
    e = Entry()
    e.add_operand(-50)
    e.add_operand(75)
    e.add_operand(-25)
    e.add_operand(100)
    e.operator_name = "BlueValues"
    assert e.get_delta() == [-50, 25, 0, 100]


def test_entry_get_delta_single_operand_is_identity() -> None:
    e = Entry()
    e.add_operand(7)
    e.operator_name = "StdHW"
    assert e.get_delta() == [7]
    # And an empty entry yields an empty list.
    assert Entry().get_delta() == []


def test_read_private_dict_nominal_width_x_defaults_to_zero() -> None:
    # Default of nominalWidthX is 0; absence of the entry in the
    # private DICT must surface that default verbatim.
    priv = CFFParser.read_private_dict(DictData())
    assert priv["nominalWidthX"] == 0
    assert priv["defaultWidthX"] == 0


def test_read_private_dict_propagates_explicit_nominal_width() -> None:
    d = DictData()
    e = Entry()
    e.operator_name = "nominalWidthX"
    e.add_operand(456)
    d.add(e)
    priv = CFFParser.read_private_dict(d)
    assert priv["nominalWidthX"] == 456
