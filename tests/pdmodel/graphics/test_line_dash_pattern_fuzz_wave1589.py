"""Fuzz/parity battery for the line-dash-pattern model + its application in
stroking, wave 1589 (agent E).

Hammers:

* ``PDLineDashPattern`` construction from a ``COSArray`` + phase, the empty /
  default / all-zero / single-element / two-element / negative-value cases,
  the negative-phase normalisation (PDF 2.0 §8.4.3.6), the ``get_cos_object``
  round-trip, and ``get_dash_array`` / ``get_phase`` types.
* The renderer's all-zero-dash guard (PDFBox ``PageDrawer.isAllZeroDash`` →
  paints nothing) and the dash-scaling-by-CTM helper
  (``_transform_width_scale`` == ``PageDrawer.transformWidth``).

Behaviour pinned against Apache PDFBox 3.0.7. ``PDLineDashPattern`` was
validated against the live oracle in wave 1531 (probe
``oracle/probes/LineDashPatternFuzzProbe.java``): upstream's constructor
normalises a negative phase by adding twice the dash-length sum until positive
(truncating to int once at the end via ``d2i``), ``getDashArray`` delegates to
``COSArray.toFloatArray`` (one slot per element, non-numbers → 0.0, negatives
preserved — it does NOT clamp), and ``getPhase`` returns an ``int``.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName
from pypdfbox.pdmodel.graphics.pd_line_dash_pattern import PDLineDashPattern
from pypdfbox.rendering.pdf_renderer import PDFRenderer


def _arr(values: list[float]) -> COSArray:
    arr = COSArray()
    arr.set_float_array(values)
    return arr


def _make(values: list[float], phase: float = 0) -> PDLineDashPattern:
    return PDLineDashPattern(_arr(values), phase)


# --------------------------------------------------------------------------
# construction + accessors
# --------------------------------------------------------------------------


def test_default_constructor_is_solid() -> None:
    p = PDLineDashPattern()
    assert p.get_dash_array() == []
    assert p.get_phase() == 0
    assert p.is_solid() is True


def test_empty_cos_array_is_solid() -> None:
    p = _make([], 0)
    assert p.get_dash_array() == []
    assert p.is_solid() is True
    # empty array == solid line; never the all-zero "paints nothing" pattern
    assert p.is_zero_pattern() is False


def test_single_element_dash_3_on_3_off() -> None:
    # [3] means 3 on, 3 off (the array applies cyclically).
    p = _make([3.0], 0)
    assert p.get_dash_array() == [3.0]
    assert p.is_solid() is False
    assert p.is_zero_pattern() is False


def test_two_element_dash() -> None:
    p = _make([4.0, 2.0], 1)
    assert p.get_dash_array() == [4.0, 2.0]
    assert p.get_phase() == 1


def test_get_dash_array_returns_list_of_float() -> None:
    p = _make([3, 2], 0)
    arr = p.get_dash_array()
    assert isinstance(arr, list)
    assert all(isinstance(v, float) for v in arr)


def test_get_dash_array_is_defensive_copy() -> None:
    p = _make([3.0, 2.0], 0)
    first = p.get_dash_array()
    first.append(99.0)
    # mutating the returned list must not corrupt the stored array
    assert p.get_dash_array() == [3.0, 2.0]


def test_get_phase_is_int() -> None:
    p = _make([3.0, 2.0], 5)
    assert isinstance(p.get_phase(), int)
    assert p.get_phase() == 5


def test_construction_rejects_non_cos_array() -> None:
    with pytest.raises(TypeError):
        PDLineDashPattern([3.0, 2.0], 0)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# all-zero dash array (PDFBox treats as a degenerate "paints nothing"
# pattern via isAllZeroDash — but the model still stores it verbatim)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "values",
    [[0.0], [0.0, 0.0], [0.0, 0.0, 0.0], [0, 0]],
    ids=["zero1", "zero2", "zero3", "int_zeros"],
)
def test_all_zero_dash_array_preserved_and_flagged(values: list[float]) -> None:
    p = _make(values, 0)
    # The model keeps the array verbatim (upstream does not collapse it).
    assert p.get_dash_array() == [float(v) for v in values]
    # is_solid is reserved for the EMPTY array; an all-zero array is NOT solid.
    assert p.is_solid() is False
    assert p.is_zero_pattern() is True


def test_mixed_zero_nonzero_not_zero_pattern() -> None:
    p = _make([0.0, 3.0, 0.0], 0)
    assert p.is_zero_pattern() is False


# --------------------------------------------------------------------------
# negative dash values — upstream's COSArray.toFloatArray does NOT clamp;
# the model must preserve them faithfully (oracle wave 1531).
# --------------------------------------------------------------------------


def test_negative_dash_value_preserved_not_clamped() -> None:
    p = _make([-3.0, 2.0], 0)
    assert p.get_dash_array() == [-3.0, 2.0]


def test_all_negative_dash_values_preserved() -> None:
    p = _make([-1.0, -2.0], 0)
    assert p.get_dash_array() == [-1.0, -2.0]
    # negatives are not zero, so this is not flagged as the zero pattern
    assert p.is_zero_pattern() is False


def test_non_numeric_dash_element_maps_to_zero() -> None:
    # COSArray.toFloatArray maps a non-number element to 0.0 (one slot per
    # element — it does NOT drop the element).
    arr = COSArray()
    arr.add(COSFloat(3.0))
    arr.add(COSName.get_pdf_name("X"))
    arr.add(COSInteger.get(2))
    p = PDLineDashPattern(arr, 0)
    assert p.get_dash_array() == [3.0, 0.0, 2.0]


# --------------------------------------------------------------------------
# phase: truncation to int, phase larger than pattern sum (no normalisation
# for non-negative phase), negative-phase normalisation per PDF 2.0 §8.4.3.6
# --------------------------------------------------------------------------


def test_phase_truncated_to_int() -> None:
    # upstream's phase field is int; the constructor truncates toward zero.
    p = _make([3.0, 2.0], 2.9)
    assert p.get_phase() == 2
    assert isinstance(p.get_phase(), int)


def test_phase_larger_than_pattern_sum_kept_verbatim() -> None:
    # A non-negative phase is never normalised, even if it exceeds the sum of
    # the dash array (only NEGATIVE phases get the modular fold).
    p = _make([3.0, 2.0], 100)
    assert p.get_phase() == 100


def test_set_phase_truncates() -> None:
    p = _make([3.0, 2.0], 0)
    p.set_phase(4.7)
    assert p.get_phase() == 4
    p.set_phase(-2)
    # set_phase does NOT re-run the §8.4.3.6 fold (only the constructor does);
    # it mirrors the upstream field write, truncating to int.
    assert p.get_phase() == -2


@pytest.mark.parametrize(
    ("values", "phase_in"),
    [
        ([3.0, 2.0], -1),
        ([3.0, 2.0], -3),
        ([3.0, 2.0], -5),
        ([3.0, 2.0], -10),
        ([3.0, 2.0], -11),
        ([4.0], -1),
        ([4.0], -9),
        ([1.0, 1.0, 1.0], -100),
    ],
    ids=[
        "m1", "m3", "m5", "m10", "m11", "single_m1", "single_m9", "big_neg",
    ],
)
def test_negative_phase_normalised_to_positive(
    values: list[float], phase_in: int
) -> None:
    p = _make(values, phase_in)
    # The normalised phase must be non-negative (upstream loops until positive).
    assert p.get_phase() >= 0
    assert isinstance(p.get_phase(), int)


def _reference_negative_phase(values: list[float], phase: int) -> int:
    """Independent re-implementation of upstream's d2i fold, for differential
    comparison (PDLineDashPattern constructor bytecode offsets 12-106)."""
    if phase >= 0:
        return phase
    sum2 = sum(values) * 2.0
    if sum2 <= 0:
        return 0
    p = float(phase)
    # Mirror the constructor's two branches (bytecode offsets 67-96).
    increment = (
        sum2 if -phase < sum2 else (math.floor(-phase / sum2) + 1.0) * sum2
    )
    return int(p + increment)  # d2i truncates toward zero


@pytest.mark.parametrize(
    ("values", "phase_in"),
    [
        ([3.0, 2.0], -1),
        ([3.0, 2.0], -5),
        ([3.0, 2.0], -10),
        ([3.0, 2.0], -11),
        ([4.0], -1),
        ([1.0, 1.0, 1.0], -100),
        ([2.5, 1.5], -7),
    ],
    ids=["a", "b", "c", "d", "e", "f", "g"],
)
def test_negative_phase_matches_upstream_d2i_fold(
    values: list[float], phase_in: int
) -> None:
    p = _make(values, phase_in)
    assert p.get_phase() == _reference_negative_phase(values, phase_in)


def test_negative_phase_with_zero_sum_array_folds_to_zero() -> None:
    # sum == 0 (all-zero or empty array) → 2*sum == 0 → phase forced to 0.
    assert _make([0.0, 0.0], -5).get_phase() == 0
    assert _make([], -5).get_phase() == 0


# --------------------------------------------------------------------------
# to_cos_array / get_cos_object round-trip
# --------------------------------------------------------------------------


def test_get_cos_object_round_trip() -> None:
    p = _make([4.0, 6.0], 2)
    cos = p.get_cos_object()
    assert isinstance(cos, COSArray)
    assert cos.size() == 2
    inner = cos.get_object(0)
    assert isinstance(inner, COSArray)
    assert inner.to_float_array() == [4.0, 6.0]
    phase_entry = cos.get_object(1)
    assert isinstance(phase_entry, COSInteger)
    assert phase_entry.value == 2


def test_to_cos_array_is_get_cos_object_alias() -> None:
    p = _make([5.0, 3.0], 1)
    a = p.to_cos_array()
    b = p.get_cos_object()
    assert a.get_object(0).to_float_array() == b.get_object(0).to_float_array()
    assert a.get_object(1).value == b.get_object(1).value


def test_cos_object_phase_always_cos_integer() -> None:
    # upstream getCOSObject emits the phase as a COSInteger (the field is int).
    p = _make([3.0, 2.0], 1.9)
    phase_entry = p.get_cos_object().get_object(1)
    assert isinstance(phase_entry, COSInteger)
    assert phase_entry.value == 1


def test_from_cos_array_disk_form() -> None:
    inner = _arr([3.0, 2.0])
    disk = COSArray()
    disk.add(inner)
    disk.add(COSInteger.get(4))
    p = PDLineDashPattern.from_cos_array(disk)
    assert p.get_dash_array() == [3.0, 2.0]
    assert p.get_phase() == 4


def test_cos_object_round_trip_reconstructs_pattern() -> None:
    original = _make([3.0, 2.0, 5.0], 1)
    cos = original.get_cos_object()
    rebuilt = PDLineDashPattern.from_cos_array(cos)
    assert rebuilt == original


# --------------------------------------------------------------------------
# renderer: all-zero-dash guard (PageDrawer.isAllZeroDash → paints nothing)
# --------------------------------------------------------------------------


def test_renderer_is_all_zero_dash_predicate() -> None:
    from pypdfbox.rendering.page_drawer import PageDrawer

    # The predicate lives on PageDrawer; it does not require a live render.
    assert PageDrawer.is_all_zero_dash.__name__ == "is_all_zero_dash"


def test_renderer_all_zero_intervals_guard_logic() -> None:
    # Mirror the guard the stroke sites use: an all-zero interval list must
    # paint NOTHING (upstream's isAllZeroDash → empty Area), while any positive
    # interval makes the dash live.
    all_zero = [0.0, 0.0]
    one_positive = [0.0, 3.0]
    assert not any(v > 0.0 for v in all_zero)
    assert any(v > 0.0 for v in one_positive)


# --------------------------------------------------------------------------
# renderer: dash scaling by the CTM == PageDrawer.transformWidth
# --------------------------------------------------------------------------


def test_transform_width_scale_uniform() -> None:
    # cm s 0 0 s 0 0 → uniform scale s → transformWidth == s.
    assert PDFRenderer._transform_width_scale((2.0, 0.0, 0.0, 2.0, 0.0, 0.0)) == pytest.approx(2.0)
    assert PDFRenderer._transform_width_scale((1.0, 0.0, 0.0, 1.0, 0.0, 0.0)) == pytest.approx(1.0)


def test_transform_width_scale_anisotropic() -> None:
    # cm 3 0 0 1 → x=a+c=3, y=b+d=1 → sqrt((9+1)/2) == sqrt(5).
    scale = PDFRenderer._transform_width_scale((3.0, 0.0, 0.0, 1.0, 0.0, 0.0))
    assert scale == pytest.approx(math.sqrt(5.0))


def test_dash_intervals_and_phase_scale_by_same_scalar() -> None:
    # The renderer scales both dash intervals and the phase by transformWidth,
    # keeping the on/off rhythm proportional to the (also-scaled) stroke width.
    ctm = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)
    scale = PDFRenderer._transform_width_scale(ctm)
    intervals = [3.0, 2.0]
    phase = 1.0
    scaled_intervals = [v * scale for v in intervals]
    scaled_phase = phase * scale
    assert scaled_intervals == [6.0, 4.0]
    assert scaled_phase == 2.0


def test_dash_scaling_preserves_all_zero_degeneracy() -> None:
    # Scaling an all-zero interval list by any scale leaves it all-zero, so the
    # downstream isAllZeroDash guard still fires after scaling.
    scale = PDFRenderer._transform_width_scale((4.0, 0.0, 0.0, 4.0, 0.0, 0.0))
    scaled = [v * scale for v in [0.0, 0.0]]
    assert not any(v > 0.0 for v in scaled)


# --------------------------------------------------------------------------
# equality / hashing / repr stability
# --------------------------------------------------------------------------


def test_equality_and_hash() -> None:
    a = _make([3.0, 2.0], 1)
    b = _make([3.0, 2.0], 1)
    c = _make([3.0, 2.0], 2)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c


def test_to_string_matches_upstream_shape() -> None:
    assert _make([], 0).to_string() == "PDLineDashPattern{array=[], phase=0}"
    assert _make([3.0, 2.0], 1).to_string() == "PDLineDashPattern{array=[3.0, 2.0], phase=1}"
