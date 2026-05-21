"""Wave 1368 — Type 2 charstring subroutine recursion + cycle behaviour.

The Type 2 charstring spec allows subroutines to call other subroutines
(both local ``callsubr`` and global ``callgsubr``). Upstream's
``Type2CharStringParser`` does not implement an explicit cycle guard —
infinite recursion raises ``StackOverflowError`` in Java and
``RecursionError`` in Python. These tests pin down:

* Linear nested subroutine calls (gsubr → lsubr).
* The ``ret`` operator being stripped at every level so the resulting
  flat sequence carries only the substantive operators.
* Self-referencing subroutines terminating via ``RecursionError``
  rather than silently hanging.
* Operand fallback: a non-integer top-of-stack pops cleanly without
  resolving a subroutine.
"""

from __future__ import annotations

import sys

import pytest

from pypdfbox.fontbox.cff.char_string_command import CharStringCommand
from pypdfbox.fontbox.cff.type2_char_string_parser import Type2CharStringParser
from pypdfbox.fontbox.cff.type2_keyword import Type2KeyWord


def test_global_subr_call_inlines_body_and_strips_ret() -> None:
    # GSubr 0: push 61 (b0=200), ret (b0=11).
    gsi = [b"\xc8\x0b"]
    # Main: push -107 (b0=32), callgsubr (b0=29), endchar (b0=14).
    # operand=-107 + bias 107 = 0 → gsubr 0.
    main = b"\x20\x1d\x0e"
    parser = Type2CharStringParser("F")
    seq = parser.parse(main, gsi, None, "")
    # After inlining: [61, endchar]. The ret must have been stripped.
    assert 61 in seq
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR
    # No bare RET command leaks into the flat sequence.
    for item in seq:
        if isinstance(item, CharStringCommand):
            assert item.get_type2_key_word() is not Type2KeyWord.RET


def test_local_subr_call_uses_local_index_not_global() -> None:
    # LSubr 0: push 50 (b0=189 = 50+139), ret.
    lsi = [b"\xbd\x0b"]
    gsi = [b"\xc8\x0b"]  # Different body — should NOT be inlined.
    # Main: push -107, callsubr (b0=10), endchar.
    main = b"\x20\x0a\x0e"
    parser = Type2CharStringParser("F")
    seq = parser.parse(main, gsi, lsi, "")
    assert 50 in seq
    assert 61 not in seq
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_nested_subr_calls_inline_both_bodies() -> None:
    # LSubr 0: push 70 (b0=209), ret.
    # GSubr 0: push -107 (b0=32), callsubr (calls lsubr 0), ret.
    lsi = [b"\xd1\x0b"]
    gsi = [b"\x20\x0a\x0b"]
    # Main: push -107, callgsubr (calls gsubr 0), endchar.
    main = b"\x20\x1d\x0e"
    parser = Type2CharStringParser("F")
    seq = parser.parse(main, gsi, lsi, "")
    # Expect 70 inlined via the chained gsubr→lsubr resolution.
    assert 70 in seq
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_subr_call_with_no_pending_operand_is_noop() -> None:
    # callgsubr with no operand on the stack: parser pops from an empty
    # sequence and short-circuits (returns None from get_subr_bytes).
    # The actual short-circuit happens *before* the pop because the
    # check ``if not glyph_data.sequence`` returns early.
    gsi = [b"\xc8\x0b"]  # Must not be reached.
    main = b"\x1d\x0e"  # callgsubr (no operand), then endchar
    parser = Type2CharStringParser("F")
    seq = parser.parse(main, gsi, None, "")
    # Only the endchar should be in the sequence; 61 must NOT appear.
    assert 61 not in seq
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_subr_call_with_float_operand_does_not_resolve() -> None:
    # Sole top-of-stack is a fixed-point float (b0=255) followed by
    # callgsubr. Per upstream behaviour, get_subr_bytes returns None
    # when the popped operand isn't an int.
    gsi = [b"\xc8\x0b"]
    # Push 1.0 (b0=255, 0x00010000 → 1 + 0/65535) then callgsubr.
    main = b"\xff\x00\x01\x00\x00\x1d\x0e"
    parser = Type2CharStringParser("F")
    seq = parser.parse(main, gsi, None, "")
    # The float remained on the stack; callgsubr inert; 61 not inlined.
    assert 61 not in seq


def test_subr_call_out_of_range_index_no_op() -> None:
    # Single gsubr → bias 107. Push operand=200 → subr_number = 307;
    # 307 >= len(gsi)==1 → get_subr_bytes returns None.
    # Encode 200: tinyint range is [-107, 107]; need 2-byte encoding.
    # (b0=247..250) → first form: b0=248, b1=0 → 1*256+0+108 = 364.
    # Actually for 200: b0=247, b1=200-108 = 92 → (0)*256+92+108=200.
    gsi = [b"\xc8\x0b"]
    main = b"\xf7\x5c\x1d\x0e"  # push 200 (b0=247, b1=92), callgsubr, endchar
    parser = Type2CharStringParser("F")
    seq = parser.parse(main, gsi, None, "")
    # 61 NOT inlined because the bias lookup misses.
    assert 61 not in seq
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR


def test_self_referencing_global_subr_terminates_via_recursion_error() -> None:
    # GSubr 0 calls itself: push -107, callgsubr, ret. With a 1-entry
    # index, operand -107 + bias 107 = 0 → recurses into the same subr.
    gsi = [b"\x20\x1d\x0b"]
    main = b"\x20\x1d\x0e"
    parser = Type2CharStringParser("F")
    # Cap recursion temporarily to avoid burning a lot of frames on
    # the parse_sequence stack.
    original = sys.getrecursionlimit()
    sys.setrecursionlimit(200)
    try:
        with pytest.raises(RecursionError):
            parser.parse(main, gsi, None, "")
    finally:
        sys.setrecursionlimit(original)


def test_mutual_subr_recursion_terminates_via_recursion_error() -> None:
    # GSubr 0: push -107, callsubr (calls lsubr 0), ret.
    # LSubr 0: push -107, callgsubr (calls gsubr 0), ret.
    # Mutual recursion gsubr ↔ lsubr.
    gsi = [b"\x20\x0a\x0b"]
    lsi = [b"\x20\x1d\x0b"]
    main = b"\x20\x1d\x0e"
    parser = Type2CharStringParser("F")
    original = sys.getrecursionlimit()
    sys.setrecursionlimit(200)
    try:
        with pytest.raises(RecursionError):
            parser.parse(main, gsi, lsi, "")
    finally:
        sys.setrecursionlimit(original)


def test_subr_with_trailing_operator_after_ret_keeps_pre_ret_operators() -> None:
    # A subr that emits multiple operators ending in ret: only the
    # final ret is stripped; intermediate operators remain.
    # GSubr 0: push 200 (=61), hlineto (b0=6), ret.
    gsi = [b"\xc8\x06\x0b"]
    main = b"\x20\x1d\x0e"  # push -107, callgsubr, endchar
    parser = Type2CharStringParser("F")
    seq = parser.parse(main, gsi, None, "")
    # Body should leave [61, HLINETO, ENDCHAR].
    cmds = [s for s in seq if isinstance(s, CharStringCommand)]
    assert any(c.get_type2_key_word() is Type2KeyWord.HLINETO for c in cmds)
    assert seq[-1].get_type2_key_word() is Type2KeyWord.ENDCHAR
