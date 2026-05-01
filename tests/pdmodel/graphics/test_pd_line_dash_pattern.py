from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern


def test_default_is_empty_with_zero_phase() -> None:
    pattern = PDLineDashPattern()
    assert pattern.get_dash_array() == []
    assert pattern.get_phase() == 0


def test_construct_with_dash_array_and_phase() -> None:
    array = COSArray()
    array.set_float_array([3, 2])
    pattern = PDLineDashPattern(array, 1.5)

    assert pattern.get_dash_array() == [3.0, 2.0]
    assert pattern.get_phase() == 1.5


def test_get_dash_array_returns_defensive_copy() -> None:
    array = COSArray()
    array.set_float_array([1, 2, 3])
    pattern = PDLineDashPattern(array, 0)

    out = pattern.get_dash_array()
    out.append(99.0)
    assert pattern.get_dash_array() == [1.0, 2.0, 3.0]


def test_get_cos_array_round_trip() -> None:
    array = COSArray()
    array.set_float_array([4.0, 6.0])
    pattern = PDLineDashPattern(array, 2)

    cos = pattern.get_cos_array()
    assert cos.size() == 2

    inner = cos.get_object(0)
    assert isinstance(inner, COSArray)
    assert inner.to_float_array() == [4.0, 6.0]

    phase_entry = cos.get_object(1)
    assert isinstance(phase_entry, COSInteger)
    assert phase_entry.value == 2

    # round-trip back via from_cos_array
    rebuilt = PDLineDashPattern.from_cos_array(cos)
    assert rebuilt == pattern
    assert rebuilt.get_dash_array() == [4.0, 6.0]
    assert rebuilt.get_phase() == 2


def test_get_cos_array_with_float_phase_uses_cos_float() -> None:
    array = COSArray()
    array.set_float_array([3.0, 2.0])
    pattern = PDLineDashPattern(array, 1.5)

    cos = pattern.get_cos_array()
    phase_entry = cos.get_object(1)
    assert isinstance(phase_entry, COSFloat)
    assert phase_entry.value == pytest.approx(1.5)


def test_get_cos_object_alias_for_get_cos_array() -> None:
    array = COSArray()
    array.set_float_array([5.0])
    pattern = PDLineDashPattern(array, 0)

    cos1 = pattern.get_cos_object()
    cos2 = pattern.get_cos_array()
    assert isinstance(cos1, COSArray)
    assert cos1.to_list() == cos2.to_list() or cos1.size() == cos2.size()


def test_negative_phase_normalised_per_pdf_2_0() -> None:
    array = COSArray()
    array.set_float_array([3.0, 5.0])  # sum * 2 == 16
    pattern = PDLineDashPattern(array, -4)
    # -4 + 16 == 12
    assert pattern.get_phase() == 12


def test_negative_phase_with_empty_array_clamps_to_zero() -> None:
    array = COSArray()
    pattern = PDLineDashPattern(array, -7)
    assert pattern.get_phase() == 0


def test_equality_and_hash() -> None:
    a = COSArray()
    a.set_float_array([1.0, 2.0])
    b = COSArray()
    b.set_float_array([1.0, 2.0])
    c = COSArray()
    c.set_float_array([2.0, 1.0])

    p1 = PDLineDashPattern(a, 3)
    p2 = PDLineDashPattern(b, 3)
    p3 = PDLineDashPattern(c, 3)

    assert p1 == p2
    assert hash(p1) == hash(p2)
    assert p1 != p3
    assert p1 != "not a pattern"


def test_init_rejects_non_cos_array() -> None:
    with pytest.raises(TypeError):
        PDLineDashPattern([1.0, 2.0], 0)  # type: ignore[arg-type]


def test_from_cos_array_requires_two_entries() -> None:
    bad = COSArray()
    bad.set_float_array([1.0, 2.0, 3.0])
    with pytest.raises(ValueError):
        PDLineDashPattern.from_cos_array(bad)


def test_from_cos_array_requires_inner_array() -> None:
    bad = COSArray()
    bad.add(COSInteger.get(1))
    bad.add(COSInteger.get(2))
    with pytest.raises(TypeError):
        PDLineDashPattern.from_cos_array(bad)


def test_str_matches_upstream_to_string_shape() -> None:
    """Mirrors upstream ``PDLineDashPattern.toString()``:
    ``PDLineDashPattern{array=[...], phase=N}``.
    Java's ``Float.toString`` always emits a trailing ``.0`` for integral
    floats, so ``new float[]{3, 2}`` renders as ``[3.0, 2.0]``.
    """
    array = COSArray()
    array.set_float_array([3, 2])
    pattern = PDLineDashPattern(array, 1)
    assert str(pattern) == "PDLineDashPattern{array=[3.0, 2.0], phase=1}"


def test_str_empty_pattern() -> None:
    pattern = PDLineDashPattern()
    assert str(pattern) == "PDLineDashPattern{array=[], phase=0}"


def test_str_includes_phase() -> None:
    array = COSArray()
    array.set_float_array([1.5])
    pattern = PDLineDashPattern(array, 0)
    text = str(pattern)
    assert text.startswith("PDLineDashPattern{array=[1.5]")
    assert text.endswith("phase=0}")
