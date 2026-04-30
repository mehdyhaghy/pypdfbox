from __future__ import annotations

from pypdfbox.cos import COSFloat


def test_construct_from_float() -> None:
    f = COSFloat(1.5)
    assert f.value == 1.5
    assert f.float_value() == 1.5
    assert f.double_value() == 1.5
    assert f.int_value() == 1
    assert f.get_original_form() is None


def test_construct_from_string_preserves_original() -> None:
    f = COSFloat("1.000")
    assert f.value == 1.0
    assert f.get_original_form() == "1.000"


def test_set_value_clears_original() -> None:
    f = COSFloat("2.500")
    f.set_value(3.0)
    assert f.value == 3.0
    assert f.get_original_form() is None


def test_pdfbox_camelcase_aliases() -> None:
    f = COSFloat("2.500")
    assert f.getValue() == 2.5
    assert f.getOriginalForm() == "2.500"

    f.setValue(3.25)

    assert f.get_value() == 3.25
    assert f.getOriginalForm() is None


def test_negative_and_scientific() -> None:
    assert COSFloat("-0.5").value == -0.5
    # COSFloat clamps to IEEE-754 single precision (Java float parity), so
    # 0.001 round-trips with the float32 representation, not the exact double.
    import math

    assert math.isclose(COSFloat("1e-3").value, 0.001, rel_tol=1e-6)


def test_int_conversion_truncates() -> None:
    assert COSFloat(2.9).int_value() == 2
    assert COSFloat(-2.9).int_value() == -2


def test_equality_uses_numeric_value_not_original() -> None:
    assert COSFloat("1.0") == COSFloat(1.0)
    assert COSFloat("1.000") == COSFloat("1.0")


def test_visitor_dispatch() -> None:
    from tests.cos.helpers import RecordingVisitor

    v = RecordingVisitor()
    f = COSFloat(0.0)
    f.accept(v)
    assert v.calls == [("float", f)]
