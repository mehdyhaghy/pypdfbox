"""Wave 1388 — verify `COSArray.of(float...)` parity with upstream."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat


def test_of_wraps_each_float_into_cos_float() -> None:
    arr = COSArray.of([1.5, -2.0, 0.0, 3.14])
    assert arr.size() == 4
    for entry in arr:
        assert isinstance(entry, COSFloat)
    assert arr.get_float(0) == 1.5
    assert arr.get_float(1) == -2.0
    assert arr.get_float(2) == 0.0
    assert abs(arr.get_float(3) - 3.14) < 1e-6


def test_of_with_int_inputs_coerces_to_float() -> None:
    arr = COSArray.of([1, 2, 3])
    assert arr.size() == 3
    for entry in arr:
        assert isinstance(entry, COSFloat)
    assert arr.get_float(1) == 2.0


def test_of_empty_iterable_returns_empty_array() -> None:
    arr = COSArray.of([])
    assert arr.size() == 0


def test_of_accepts_tuple_and_generator() -> None:
    arr_tuple = COSArray.of((1.0, 2.0))
    assert arr_tuple.size() == 2
    arr_gen = COSArray.of(float(x) for x in range(3))
    assert arr_gen.size() == 3
    assert arr_gen.get_float(2) == 2.0
