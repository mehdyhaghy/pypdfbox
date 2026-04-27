from __future__ import annotations

import struct

from pypdfbox.cos import COSBoolean, COSFloat, COSName


# ---------------------------------------------------------------------------
# COSBoolean — get_value / is_true / is_false / __bool__ round-trip
# ---------------------------------------------------------------------------


def test_boolean_get_value_round_trip() -> None:
    assert COSBoolean.TRUE.get_value() is True
    assert COSBoolean.FALSE.get_value() is False


def test_boolean_is_true_is_false() -> None:
    assert COSBoolean.TRUE.is_true() is True
    assert COSBoolean.TRUE.is_false() is False
    assert COSBoolean.FALSE.is_true() is False
    assert COSBoolean.FALSE.is_false() is True


def test_boolean_bool_protocol_round_trip() -> None:
    assert bool(COSBoolean.TRUE) is True
    assert bool(COSBoolean.FALSE) is False


def test_boolean_get_boolean_factory() -> None:
    assert COSBoolean.get_boolean(True) is COSBoolean.TRUE
    assert COSBoolean.get_boolean(False) is COSBoolean.FALSE
    # And consistent with the value-based predicates
    assert COSBoolean.get_boolean(True).is_true()
    assert COSBoolean.get_boolean(False).is_false()


# ---------------------------------------------------------------------------
# COSName — KIDS / FIRST_CHAR / LAST_CHAR / WIDTHS resolve to interned
# COSName instances with the expected upstream string.
# ---------------------------------------------------------------------------


def test_cos_name_constants_resolve() -> None:
    cases = [
        (COSName.KIDS, "Kids"),
        (COSName.FIRST_CHAR, "FirstChar"),
        (COSName.LAST_CHAR, "LastChar"),
        (COSName.WIDTHS, "Widths"),
    ]
    for constant, expected in cases:
        assert isinstance(constant, COSName)
        assert constant.get_name() == expected
        assert constant.name == expected
        # Interned: re-fetch returns the exact same instance.
        assert COSName.get_pdf_name(expected) is constant


# ---------------------------------------------------------------------------
# COSFloat — int_value / long_value / float_value / double_value /
# get_value all consistent.
# ---------------------------------------------------------------------------


def test_cos_float_value_accessors_consistent() -> None:
    f = COSFloat(3.5)
    assert f.float_value() == 3.5
    assert f.double_value() == 3.5
    assert f.get_value() == 3.5
    assert f.value == 3.5
    assert f.int_value() == 3
    assert f.long_value() == 3
    # All numeric accessors agree with each other.
    assert f.float_value() == f.double_value() == f.get_value() == f.value
    assert f.int_value() == f.long_value() == int(f.value)


def test_cos_float_value_accessors_negative_truncates_toward_zero() -> None:
    f = COSFloat(-2.75)
    assert f.float_value() == -2.75
    assert f.double_value() == -2.75
    assert f.get_value() == -2.75
    # Python int() truncates toward zero, mirroring Java (int)/(long) cast.
    assert f.int_value() == -2
    assert f.long_value() == -2


# ---------------------------------------------------------------------------
# COSFloat — set_value clamps to single (32-bit IEEE-754) precision.
# ---------------------------------------------------------------------------


def _to_float32(x: float) -> float:
    return float(struct.unpack(">f", struct.pack(">f", x))[0])


def test_cos_float_set_value_clamps_to_single_precision() -> None:
    f = COSFloat(0.0)
    # 0.1 has no exact float32 representation; setting it must round to
    # the nearest float32 value, not preserve full float64.
    f.set_value(0.1)
    assert f.get_value() == _to_float32(0.1)
    # Sanity: the float32 round-trip of 0.1 is *not* exactly equal to the
    # float64 0.1, otherwise the test would prove nothing.
    assert _to_float32(0.1) != 0.1
    # All accessor methods see the clamped value.
    assert f.float_value() == _to_float32(0.1)
    assert f.double_value() == _to_float32(0.1)
    assert f.value == _to_float32(0.1)


def test_cos_float_set_value_preserves_exact_representable_values() -> None:
    f = COSFloat(0.0)
    # 0.5 is exactly representable in float32, so clamping is a no-op.
    f.set_value(0.5)
    assert f.get_value() == 0.5
    assert f.float_value() == 0.5
    assert f.int_value() == 0
    assert f.long_value() == 0


def test_cos_float_set_value_resets_original_form() -> None:
    f = COSFloat("1.25")
    assert f.get_original_form() == "1.25"
    f.set_value(2.0)
    # Per existing semantics, set_value invalidates the parsed-text form.
    assert f.get_original_form() is None
    assert f.get_value() == 2.0
