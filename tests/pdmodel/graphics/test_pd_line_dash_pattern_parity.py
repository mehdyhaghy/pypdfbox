from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern


def _make(values: list[float], phase: float = 0) -> PDLineDashPattern:
    arr = COSArray()
    arr.set_float_array(values)
    return PDLineDashPattern(arr, phase)


def test_get_dash_array_round_trip() -> None:
    pattern = _make([3.0, 2.0, 5.0], 0)
    assert pattern.get_dash_array() == [3.0, 2.0, 5.0]


def test_set_dash_array_round_trip() -> None:
    pattern = PDLineDashPattern()
    pattern.set_dash_array([1.0, 4.0, 2.0])
    assert pattern.get_dash_array() == [1.0, 4.0, 2.0]

    # mutating the input list later should not affect the stored copy
    incoming = [7.0, 8.0]
    pattern.set_dash_array(incoming)
    incoming.append(99.0)
    assert pattern.get_dash_array() == [7.0, 8.0]


def test_set_dash_array_with_none_clears() -> None:
    pattern = _make([1.0, 2.0], 0)
    pattern.set_dash_array(None)  # type: ignore[arg-type]
    assert pattern.get_dash_array() == []
    assert pattern.is_solid() is True


def test_get_set_phase_round_trip() -> None:
    pattern = _make([3.0, 2.0], 0)
    assert pattern.get_phase() == 0

    pattern.set_phase(2.5)
    assert pattern.get_phase() == 2.5

    pattern.set_phase(7)
    assert pattern.get_phase() == 7


def test_is_solid_true_for_empty_pattern() -> None:
    pattern = PDLineDashPattern()
    assert pattern.is_solid() is True

    pattern2 = _make([], 0)
    assert pattern2.is_solid() is True

    not_solid = _make([3.0, 2.0], 0)
    assert not_solid.is_solid() is False


def test_is_zero_pattern_true_when_all_entries_zero() -> None:
    pattern = _make([0.0, 0.0, 0.0], 0)
    assert pattern.is_zero_pattern() is True

    mixed = _make([0.0, 1.0, 0.0], 0)
    assert mixed.is_zero_pattern() is False

    nonzero = _make([3.0, 2.0], 0)
    assert nonzero.is_zero_pattern() is False


def test_get_cos_object_returns_cos_array_of_dash_array_and_phase() -> None:
    pattern = _make([4.0, 6.0], 2)
    cos = pattern.get_cos_object()

    assert isinstance(cos, COSArray)
    assert cos.size() == 2

    inner = cos.get_object(0)
    assert isinstance(inner, COSArray)
    assert inner.to_float_array() == [4.0, 6.0]

    phase_entry = cos.get_object(1)
    assert isinstance(phase_entry, COSInteger)
    assert phase_entry.value == 2


def test_get_cos_object_with_float_phase() -> None:
    pattern = _make([3.0, 2.0], 1.5)
    cos = pattern.get_cos_object()
    phase_entry = cos.get_object(1)
    assert isinstance(phase_entry, COSFloat)
    assert phase_entry.value == 1.5


def test_to_cos_array_alias() -> None:
    pattern = _make([5.0, 3.0], 1)
    via_obj = pattern.get_cos_object()
    via_alias = pattern.to_cos_array()
    assert isinstance(via_alias, COSArray)
    assert via_alias.size() == via_obj.size()
    assert via_alias.get_object(0).to_float_array() == via_obj.get_object(0).to_float_array()
    assert via_alias.get_object(1).value == via_obj.get_object(1).value
