"""Fuzz / parity tests for the line-state content-stream operators —
wave 1571.

Targets ``J`` (cap), ``j`` (join), ``M`` (miter limit), ``w`` (width),
and ``d`` (dash pattern) under
``pypdfbox/contentstream/operator/state``. The first three were only
~71% covered: the previously-untested branches are the graphics-state
*application* path (where the resulting ``set_line_cap`` /
``set_line_join`` / ``set_miter_limit`` value is actually asserted), the
non-numeric silent-skip guard, and the float-operand path.

Every case is pinned against upstream PDFBox 3.0.7 Java behaviour:

* ``SetLineCapStyle`` / ``SetLineJoinStyle`` / ``SetLineMiterLimit`` /
  ``SetLineWidth`` all: throw ``MissingOperandException`` on empty
  operands; ``checkArrayTypesClass(arguments, COSNumber.class)`` over the
  WHOLE list and silently ``return`` if any operand is non-numeric; then
  apply ``arguments.get(0)`` to the graphics state with **no range
  clamp** (cap=99, negative miter, etc. flow straight through).
* ``SetLineDashPattern`` (``d``): throw on fewer than 2 operands; silent
  ``return`` if operand 0 is not a ``COSArray`` or operand 1 is not a
  ``COSNumber``; sanitise the dash array by breaking on the first
  non-zero number, replacing with an empty array only when a non-number
  entry is reached first.
"""

from __future__ import annotations

import pytest

from pypdfbox.contentstream.operator import MissingOperandException, Operator
from pypdfbox.contentstream.operator.state.set_line_cap_style import (
    SetLineCapStyle,
)
from pypdfbox.contentstream.operator.state.set_line_dash_pattern import (
    SetLineDashPattern,
)
from pypdfbox.contentstream.operator.state.set_line_join_style import (
    SetLineJoinStyle,
)
from pypdfbox.contentstream.operator.state.set_line_miter_limit import (
    SetLineMiterLimit,
)
from pypdfbox.contentstream.operator.state.set_line_width import SetLineWidth
from pypdfbox.cos import (
    COSArray,
    COSFloat,
    COSInteger,
    COSName,
    COSString,
)
from pypdfbox.pdmodel.graphics.state.pd_graphics_state import PDGraphicsState


class _StubEngine:
    """Minimal stand-in for ``PDFStreamEngine`` exposing only the surface
    the line-state operators touch: ``get_graphics_state`` plus the
    ``set_line_dash_pattern`` notification hook."""

    def __init__(self) -> None:
        self._graphics_state = PDGraphicsState()
        self.dash_calls: list[tuple[COSArray, int]] = []

    def get_graphics_state(self) -> PDGraphicsState:
        return self._graphics_state

    def set_line_dash_pattern(self, array: COSArray, phase: int) -> None:
        self.dash_calls.append((array, phase))


def _bound(processor_cls: type) -> tuple[object, _StubEngine]:
    engine = _StubEngine()
    proc = processor_cls()
    proc.set_context(engine)
    return proc, engine


def _array(*values: float) -> COSArray:
    arr = COSArray()
    for v in values:
        arr.add(COSInteger.get(int(v)) if float(v).is_integer() else COSFloat(v))
    return arr


# --------------------------------------------------------------------------
# J — set line cap style
# --------------------------------------------------------------------------


@pytest.mark.parametrize("cap", [0, 1, 2], ids=["butt", "round", "square"])
def test_cap_applies_each_iso_value(cap: int) -> None:
    proc, engine = _bound(SetLineCapStyle)
    proc.process(Operator.get_operator("J"), [COSInteger.get(cap)])
    assert engine.get_graphics_state().get_line_cap() == cap


def test_cap_out_of_range_stored_unclamped() -> None:
    # Upstream stores the raw int — no {0,1,2} clamp.
    proc, engine = _bound(SetLineCapStyle)
    proc.process(Operator.get_operator("J"), [COSInteger.get(3)])
    assert engine.get_graphics_state().get_line_cap() == 3


def test_cap_negative_stored_unclamped() -> None:
    proc, engine = _bound(SetLineCapStyle)
    proc.process(Operator.get_operator("J"), [COSInteger.get(-5)])
    assert engine.get_graphics_state().get_line_cap() == -5


def test_cap_float_operand_truncated_via_int_value() -> None:
    proc, engine = _bound(SetLineCapStyle)
    proc.process(Operator.get_operator("J"), [COSFloat(2.9)])
    # int_value() truncates toward zero, matching Java intValue().
    assert engine.get_graphics_state().get_line_cap() == 2


def test_cap_missing_operand_raises() -> None:
    proc, _ = _bound(SetLineCapStyle)
    with pytest.raises(MissingOperandException):
        proc.process(Operator.get_operator("J"), [])


def test_cap_name_operand_silently_ignored() -> None:
    proc, engine = _bound(SetLineCapStyle)
    before = engine.get_graphics_state().get_line_cap()
    proc.process(Operator.get_operator("J"), [COSName.get_pdf_name("Bad")])
    assert engine.get_graphics_state().get_line_cap() == before


def test_cap_trailing_junk_operand_drops_whole_update() -> None:
    # checkArrayTypesClass inspects the WHOLE list → a trailing non-number
    # aborts the apply, leaving the state untouched.
    proc, engine = _bound(SetLineCapStyle)
    before = engine.get_graphics_state().get_line_cap()
    proc.process(
        Operator.get_operator("J"),
        [COSInteger.get(2), COSName.get_pdf_name("X")],
    )
    assert engine.get_graphics_state().get_line_cap() == before


# --------------------------------------------------------------------------
# j — set line join style
# --------------------------------------------------------------------------


@pytest.mark.parametrize("join", [0, 1, 2], ids=["miter", "round", "bevel"])
def test_join_applies_each_iso_value(join: int) -> None:
    proc, engine = _bound(SetLineJoinStyle)
    proc.process(Operator.get_operator("j"), [COSInteger.get(join)])
    assert engine.get_graphics_state().get_line_join() == join


def test_join_out_of_range_stored_unclamped() -> None:
    proc, engine = _bound(SetLineJoinStyle)
    proc.process(Operator.get_operator("j"), [COSInteger.get(7)])
    assert engine.get_graphics_state().get_line_join() == 7


def test_join_float_operand_truncated() -> None:
    proc, engine = _bound(SetLineJoinStyle)
    proc.process(Operator.get_operator("j"), [COSFloat(1.6)])
    assert engine.get_graphics_state().get_line_join() == 1


def test_join_missing_operand_raises() -> None:
    proc, _ = _bound(SetLineJoinStyle)
    with pytest.raises(MissingOperandException):
        proc.process(Operator.get_operator("j"), [])


def test_join_string_operand_silently_ignored() -> None:
    proc, engine = _bound(SetLineJoinStyle)
    before = engine.get_graphics_state().get_line_join()
    proc.process(Operator.get_operator("j"), [COSString("nope")])
    assert engine.get_graphics_state().get_line_join() == before


# --------------------------------------------------------------------------
# M — set miter limit
# --------------------------------------------------------------------------


def test_miter_applies_float() -> None:
    proc, engine = _bound(SetLineMiterLimit)
    proc.process(Operator.get_operator("M"), [COSFloat(10.0)])
    assert engine.get_graphics_state().get_miter_limit() == pytest.approx(10.0)


def test_miter_applies_integer_operand() -> None:
    proc, engine = _bound(SetLineMiterLimit)
    proc.process(Operator.get_operator("M"), [COSInteger.get(4)])
    assert engine.get_graphics_state().get_miter_limit() == pytest.approx(4.0)


def test_miter_negative_stored_unclamped() -> None:
    proc, engine = _bound(SetLineMiterLimit)
    proc.process(Operator.get_operator("M"), [COSFloat(-3.5)])
    assert engine.get_graphics_state().get_miter_limit() == pytest.approx(-3.5)


def test_miter_huge_value_stored() -> None:
    proc, engine = _bound(SetLineMiterLimit)
    proc.process(Operator.get_operator("M"), [COSFloat(1.0e9)])
    assert engine.get_graphics_state().get_miter_limit() == pytest.approx(1.0e9)


def test_miter_missing_operand_raises() -> None:
    proc, _ = _bound(SetLineMiterLimit)
    with pytest.raises(MissingOperandException):
        proc.process(Operator.get_operator("M"), [])


def test_miter_name_operand_silently_ignored() -> None:
    proc, engine = _bound(SetLineMiterLimit)
    before = engine.get_graphics_state().get_miter_limit()
    proc.process(Operator.get_operator("M"), [COSName.get_pdf_name("Bad")])
    assert engine.get_graphics_state().get_miter_limit() == before


# --------------------------------------------------------------------------
# w — set line width
# --------------------------------------------------------------------------


def test_width_applies_float() -> None:
    proc, engine = _bound(SetLineWidth)
    proc.process(Operator.get_operator("w"), [COSFloat(2.5)])
    assert engine.get_graphics_state().get_line_width() == pytest.approx(2.5)


def test_width_applies_integer_operand() -> None:
    proc, engine = _bound(SetLineWidth)
    proc.process(Operator.get_operator("w"), [COSInteger.get(3)])
    assert engine.get_graphics_state().get_line_width() == pytest.approx(3.0)


def test_width_zero_allowed() -> None:
    # 0 width is the device-thinnest line — a valid value, applied as-is.
    proc, engine = _bound(SetLineWidth)
    proc.process(Operator.get_operator("w"), [COSInteger.get(0)])
    assert engine.get_graphics_state().get_line_width() == pytest.approx(0.0)


def test_width_missing_operand_raises() -> None:
    proc, _ = _bound(SetLineWidth)
    with pytest.raises(MissingOperandException):
        proc.process(Operator.get_operator("w"), [])


def test_width_name_operand_silently_ignored() -> None:
    proc, engine = _bound(SetLineWidth)
    before = engine.get_graphics_state().get_line_width()
    proc.process(Operator.get_operator("w"), [COSName.get_pdf_name("Bad")])
    assert engine.get_graphics_state().get_line_width() == before


def test_width_trailing_junk_drops_update() -> None:
    proc, engine = _bound(SetLineWidth)
    before = engine.get_graphics_state().get_line_width()
    proc.process(
        Operator.get_operator("w"),
        [COSFloat(5.0), COSName.get_pdf_name("X")],
    )
    assert engine.get_graphics_state().get_line_width() == before


def test_width_get_line_width_helper_returns_none_on_empty() -> None:
    assert SetLineWidth().get_line_width([]) is None


def test_width_get_line_width_helper_returns_first_number() -> None:
    first = COSFloat(1.25)
    assert SetLineWidth().get_line_width([first]) is first


# --------------------------------------------------------------------------
# d — set line dash pattern
# --------------------------------------------------------------------------


def test_dash_two_operand_form_notifies_engine() -> None:
    proc, engine = _bound(SetLineDashPattern)
    arr = _array(3, 2)
    proc.process(Operator.get_operator("d"), [arr, COSInteger.get(1)])
    assert len(engine.dash_calls) == 1
    sent_array, sent_phase = engine.dash_calls[0]
    assert list(sent_array) == list(arr)
    assert sent_phase == 1


def test_dash_zero_phase() -> None:
    proc, engine = _bound(SetLineDashPattern)
    proc.process(Operator.get_operator("d"), [_array(4), COSInteger.get(0)])
    assert engine.dash_calls[0][1] == 0


def test_dash_phase_float_truncated_via_int_value() -> None:
    proc, engine = _bound(SetLineDashPattern)
    proc.process(Operator.get_operator("d"), [_array(4), COSFloat(2.8)])
    assert engine.dash_calls[0][1] == 2


def test_dash_empty_array_solid_line() -> None:
    proc, engine = _bound(SetLineDashPattern)
    empty = COSArray()
    proc.process(Operator.get_operator("d"), [empty, COSInteger.get(0)])
    # Empty array loops zero times → passed through untouched.
    assert list(engine.dash_calls[0][0]) == []


def test_dash_all_zero_array_passed_through() -> None:
    # All entries compare equal to 0: loop never breaks, no non-number
    # reached → original (all-zero) array forwarded as-is.
    proc, engine = _bound(SetLineDashPattern)
    proc.process(Operator.get_operator("d"), [_array(0, 0), COSInteger.get(0)])
    sent = engine.dash_calls[0][0]
    assert sent.size() == 2


def test_dash_leading_nonzero_keeps_array() -> None:
    # First entry is non-zero → loop breaks immediately, array kept.
    proc, engine = _bound(SetLineDashPattern)
    proc.process(Operator.get_operator("d"), [_array(3, 2), COSInteger.get(0)])
    assert engine.dash_calls[0][0].size() == 2


def test_dash_nonzero_then_nonnumber_keeps_array() -> None:
    # [3 /Bogus]: the loop breaks at 3 before reaching the bad element,
    # so the array is kept intact (parity-critical early-break case).
    proc, engine = _bound(SetLineDashPattern)
    arr = COSArray()
    arr.add(COSInteger.get(3))
    arr.add(COSName.get_pdf_name("Bogus"))
    proc.process(Operator.get_operator("d"), [arr, COSInteger.get(0)])
    assert engine.dash_calls[0][0].size() == 2


def test_dash_zero_then_nonnumber_becomes_empty() -> None:
    # [0 /Bogus]: zero doesn't break, the non-number is reached → array
    # replaced with an empty (solid) one.
    proc, engine = _bound(SetLineDashPattern)
    arr = COSArray()
    arr.add(COSInteger.get(0))
    arr.add(COSName.get_pdf_name("Bogus"))
    proc.process(Operator.get_operator("d"), [arr, COSInteger.get(0)])
    assert list(engine.dash_calls[0][0]) == []


def test_dash_leading_nonnumber_becomes_empty() -> None:
    proc, engine = _bound(SetLineDashPattern)
    arr = COSArray()
    arr.add(COSName.get_pdf_name("Bogus"))
    arr.add(COSInteger.get(3))
    proc.process(Operator.get_operator("d"), [arr, COSInteger.get(0)])
    assert list(engine.dash_calls[0][0]) == []


def test_dash_single_operand_raises() -> None:
    proc, _ = _bound(SetLineDashPattern)
    with pytest.raises(MissingOperandException):
        proc.process(Operator.get_operator("d"), [_array(3)])


def test_dash_empty_operands_raises() -> None:
    proc, _ = _bound(SetLineDashPattern)
    with pytest.raises(MissingOperandException):
        proc.process(Operator.get_operator("d"), [])


def test_dash_first_operand_not_array_silently_skipped() -> None:
    proc, engine = _bound(SetLineDashPattern)
    proc.process(
        Operator.get_operator("d"),
        [COSInteger.get(3), COSInteger.get(0)],
    )
    assert engine.dash_calls == []


def test_dash_second_operand_not_number_silently_skipped() -> None:
    proc, engine = _bound(SetLineDashPattern)
    proc.process(
        Operator.get_operator("d"),
        [_array(3, 2), COSName.get_pdf_name("X")],
    )
    assert engine.dash_calls == []


def test_dash_no_context_does_not_raise() -> None:
    # Standalone (registry-only) use: no engine bound → silent no-op.
    SetLineDashPattern().process(
        Operator.get_operator("d"), [_array(3, 2), COSInteger.get(0)]
    )


def test_dash_get_name() -> None:
    assert SetLineDashPattern().get_name() == "d"
