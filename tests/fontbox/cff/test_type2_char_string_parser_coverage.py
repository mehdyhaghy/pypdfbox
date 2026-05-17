"""Coverage-boost tests for
:mod:`pypdfbox.fontbox.cff.type2_char_string_parser`.

Targets the still-uncovered branches after wave 1330:

* the ``parse_sequence`` dispatch arms for ``callsubr`` (line 79) and
  ``callgsubr`` (line 81), reached only when ``parse_sequence`` itself
  encounters the opcodes (existing tests call ``process_call_subr``
  directly);
* ``get_subr_bytes`` non-int operand short-circuit (line 155);
* ``read_number`` truncation paths for the 247-250, 251-254 two-byte
  ranges (lines 228-238) and the 255 four-byte fixed-point range
  (lines 240-242);
* ``read_number`` positive / negative 2-byte happy paths
  (lines 232, 238);
* ``read_number`` invalid-byte raise (lines 246-247) — reachable via
  direct call even though ``parse_sequence`` filters it out.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type1_keyword import Key
from pypdfbox.fontbox.cff.type2_char_string_parser import (
    Type2CharStringParser,
    _GlyphData,
)
from pypdfbox.fontbox.cff.type2_keyword import Type2KeyWord

# ---------- parse_sequence subroutine dispatch arms -----------------------

def test_parse_sequence_callsubr_dispatch() -> None:
    """Hit line 79 — the ``b0 == _CALLSUBR`` arm in ``parse_sequence``."""
    parser = Type2CharStringParser("F")
    gd = _GlyphData(sequence=[-107])  # subr index 0
    # subr[0] just appends endchar (op 14).
    subrs = [bytes([14])]
    data = bytes([Key.CALLSUBR.hash_value])
    parser.parse_sequence(data, [], subrs, gd)
    assert gd.sequence
    assert gd.sequence[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_parse_sequence_callgsubr_dispatch() -> None:
    """Hit line 81 — the ``b0 == _CALLGSUBR`` arm in ``parse_sequence``."""
    parser = Type2CharStringParser("F")
    gd = _GlyphData(sequence=[-107])
    gsubrs = [bytes([14])]
    data = bytes([Key.CALLGSUBR.hash_value])
    parser.parse_sequence(data, gsubrs, [], gd)
    assert gd.sequence[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_parse_sequence_callsubr_without_local_index_no_op() -> None:
    # lsi empty → ``process_call_subr`` returns early without consuming
    # anything. The opcode byte itself is consumed but no command is
    # emitted.
    parser = Type2CharStringParser("F")
    gd = _GlyphData(sequence=[-107])  # operand stays untouched
    data = bytes([Key.CALLSUBR.hash_value])
    parser.parse_sequence(data, [], [], gd)
    # Sequence unchanged because process_call_subr bails on empty lsi.
    assert gd.sequence == [-107]


def test_parse_sequence_callgsubr_without_global_index_no_op() -> None:
    parser = Type2CharStringParser("F")
    gd = _GlyphData(sequence=[-107])
    data = bytes([Key.CALLGSUBR.hash_value])
    parser.parse_sequence(data, [], [], gd)
    assert gd.sequence == [-107]


# ---------- get_subr_bytes non-int operand --------------------------------

def test_get_subr_bytes_non_int_operand_returns_none() -> None:
    """Hit line 155 — operand not an int → bail out."""
    parser = Type2CharStringParser("F")
    # A CharStringCommand on top of the stack — not an int.
    gd = _GlyphData(sequence=[CharStringCommand.get_instance(14)])
    assert parser.get_subr_bytes([b"\x0e"], gd) is None


def test_get_subr_bytes_float_operand_returns_none() -> None:
    parser = Type2CharStringParser("F")
    gd = _GlyphData(sequence=[3.14])
    assert parser.get_subr_bytes([b"\x0e"], gd) is None


# ---------- read_number happy paths for 247-250 / 251-254 -----------------

def test_read_number_two_byte_positive_247_zero() -> None:
    parser = Type2CharStringParser("F")
    # b0 = 247, b1 = 0 → (0 * 256) + 0 + 108 = 108.
    value, new_i = parser.read_number(bytes([247, 0]), 1, 247)
    assert value == 108
    assert new_i == 2


def test_read_number_two_byte_positive_250_max() -> None:
    parser = Type2CharStringParser("F")
    # b0 = 250, b1 = 255 → (3 * 256) + 255 + 108 = 1131.
    value, new_i = parser.read_number(bytes([250, 255]), 1, 250)
    assert value == 1131


def test_read_number_two_byte_negative_251_zero() -> None:
    parser = Type2CharStringParser("F")
    value, new_i = parser.read_number(bytes([251, 0]), 1, 251)
    assert value == -108
    assert new_i == 2


def test_read_number_two_byte_negative_254_max() -> None:
    parser = Type2CharStringParser("F")
    # b0 = 254, b1 = 255 → -(3 * 256) - 255 - 108 = -1131.
    value, new_i = parser.read_number(bytes([254, 255]), 1, 254)
    assert value == -1131


# ---------- read_number truncation paths ----------------------------------

def test_read_number_two_byte_positive_truncated_247() -> None:
    """Hit lines 228-230 — 247-250 truncated."""
    parser = Type2CharStringParser("F")
    with pytest.raises(ValueError, match="Truncated"):
        parser.read_number(bytes([247]), 1, 247)


def test_read_number_two_byte_negative_truncated_251() -> None:
    """Hit lines 234-236 — 251-254 truncated."""
    parser = Type2CharStringParser("F")
    with pytest.raises(ValueError, match="Truncated"):
        parser.read_number(bytes([251]), 1, 251)


def test_read_number_fixed_truncated_at_offset() -> None:
    """Hit lines 240-242 — 255 truncated."""
    parser = Type2CharStringParser("F")
    with pytest.raises(ValueError, match="Truncated"):
        parser.read_number(bytes([255, 0x00, 0x01, 0x00]), 1, 255)


def test_read_number_invalid_byte_raises() -> None:
    """Hit lines 246-247 — unknown b0 (reachable only via direct call)."""
    parser = Type2CharStringParser("F")
    # 31 is a valid command, not an operand; passing it as b0 here
    # exercises the trailing ``raise`` arm because the read_number
    # ranges (28, 32-255) don't cover it.
    with pytest.raises(ValueError, match="Invalid Type 2 operand byte"):
        parser.read_number(bytes([31]), 1, 31)


# ---------- read_number happy paths for already-covered ranges -----------

def test_read_number_one_byte_range() -> None:
    parser = Type2CharStringParser("F")
    # b0 = 139 → 0
    value, new_i = parser.read_number(bytes([139]), 1, 139)
    assert value == 0
    assert new_i == 1


def test_read_number_one_byte_range_min() -> None:
    parser = Type2CharStringParser("F")
    # b0 = 32 → 32 - 139 = -107
    value, new_i = parser.read_number(bytes([32]), 1, 32)
    assert value == -107


def test_read_number_one_byte_range_max() -> None:
    parser = Type2CharStringParser("F")
    # b0 = 246 → 246 - 139 = 107
    value, new_i = parser.read_number(bytes([246]), 1, 246)
    assert value == 107


# ---------- parse() top-level wraps parse_sequence -----------------------

def test_parse_with_none_subr_indexes_uses_empty_lists() -> None:
    parser = Type2CharStringParser("F")
    seq = parser.parse(bytes([14]), None, None, "g")
    assert seq[0].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_parse_with_supplied_global_subr_index() -> None:
    parser = Type2CharStringParser("F")
    # subrs has length 1, so calculate_subr_number returns 107 + operand.
    # To land on index 0 we need operand == -107; b0=32 encodes -107 per
    # the one-byte range (b0 - 139).
    subrs = [bytes([14])]
    data = bytes([Key.CALLGSUBR.hash_value])
    payload = bytes([32]) + data
    seq = parser.parse(payload, subrs, None, "g")
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


# ---------- mask handling within parse_sequence --------------------------

def test_parse_sequence_cntrmask_advances_past_mask_bytes() -> None:
    """Exercises the _CNTRMASK branch (line 82) plus the mask-byte skip."""
    parser = Type2CharStringParser("F")
    gd = _GlyphData(hstem_count=4, vstem_count=4)
    # cntrmask op = 20 (Key.CNTRMASK.hash_value). 8 hints → 1 mask byte.
    data = bytes([Key.CNTRMASK.hash_value, 0xFF, 14])  # mask + endchar
    parser.parse_sequence(data, [], [], gd)
    # Final command should be endchar (not 0xFF misparsed as operand).
    assert gd.sequence[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_parse_sequence_hintmask_skips_mask_then_continues() -> None:
    parser = Type2CharStringParser("F")
    gd = _GlyphData(hstem_count=1, vstem_count=0)
    # hintmask op = 19; 1 hint → 1 mask byte.
    data = bytes([Key.HINTMASK.hash_value, 0xAB, 14])
    parser.parse_sequence(data, [], [], gd)
    assert gd.sequence[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR
