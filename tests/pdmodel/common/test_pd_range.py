"""Hand-written tests for :class:`pypdfbox.pdmodel.common.PDRange`."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSString
from pypdfbox.pdmodel.common import PDRange

# ---------- construction ----------


def test_default_constructor_creates_zero_one_range() -> None:
    rng = PDRange()
    assert rng.get_min() == 0.0
    assert rng.get_max() == 1.0
    assert rng.get_starting_index() == 0


def test_default_constructor_allocates_fresh_array() -> None:
    a = PDRange()
    b = PDRange()
    # Each PDRange owns its own backing array — mutating one must not
    # leak into the other.
    a.set_max(5.0)
    assert b.get_max() == 1.0
    assert a.get_cos_array() is not b.get_cos_array()


def test_array_constructor_uses_starting_index_zero_by_default() -> None:
    array = COSArray([COSFloat(2.0), COSFloat(7.0)])
    rng = PDRange(array)
    assert rng.get_starting_index() == 0
    assert rng.get_min() == 2.0
    assert rng.get_max() == 7.0


def test_array_constructor_with_index_selects_pair() -> None:
    # [L_min L_max a_min a_max b_min b_max] — three back-to-back ranges.
    array = COSArray(
        [
            COSFloat(0.0),
            COSFloat(100.0),
            COSFloat(-128.0),
            COSFloat(127.0),
            COSFloat(-128.0),
            COSFloat(127.0),
        ]
    )
    a_range = PDRange(array, 1)
    assert a_range.get_min() == -128.0
    assert a_range.get_max() == 127.0
    b_range = PDRange(array, 2)
    assert b_range.get_min() == -128.0
    assert b_range.get_max() == 127.0


def test_array_constructor_rejects_non_array() -> None:
    with pytest.raises(TypeError):
        PDRange(COSString(b"not an array"))  # type: ignore[arg-type]


def test_set_starting_index_retargets_pair() -> None:
    array = COSArray(
        [COSFloat(0.0), COSFloat(1.0), COSFloat(10.0), COSFloat(20.0)]
    )
    rng = PDRange(array, 0)
    assert rng.get_min() == 0.0
    rng.set_starting_index(1)
    assert rng.get_min() == 10.0
    assert rng.get_max() == 20.0


# ---------- accessors ----------


def test_set_min_updates_array() -> None:
    rng = PDRange()
    rng.set_min(-3.5)
    assert rng.get_min() == -3.5
    # Round-trip through the underlying array.
    assert isinstance(rng.get_cos_array().get_object(0), COSFloat)


def test_set_max_updates_array() -> None:
    rng = PDRange()
    rng.set_max(99.0)
    assert rng.get_max() == 99.0


def test_get_min_max_accept_cos_integer() -> None:
    # PDF 32000-1 lets entries be either real or int — both reach
    # ``COSNumber.float_value`` cleanly.
    array = COSArray([COSInteger(0), COSInteger(255)])
    rng = PDRange(array)
    assert rng.get_min() == 0.0
    assert rng.get_max() == 255.0


def test_get_min_raises_for_non_number_entry() -> None:
    array = COSArray([COSString(b"oops"), COSFloat(1.0)])
    rng = PDRange(array)
    with pytest.raises(TypeError, match="get_min"):
        rng.get_min()


def test_get_max_raises_for_non_number_entry() -> None:
    array = COSArray([COSFloat(0.0), COSString(b"oops")])
    rng = PDRange(array)
    with pytest.raises(TypeError, match="get_max"):
        rng.get_max()


def test_starting_index_offsets_array_writes() -> None:
    # Writes via set_min / set_max must land at the correct pair offset.
    array = COSArray(
        [COSFloat(0.0), COSFloat(1.0), COSFloat(2.0), COSFloat(3.0)]
    )
    rng = PDRange(array, 1)
    rng.set_min(7.0)
    rng.set_max(8.0)
    assert array.get_object(0) == COSFloat(0.0)
    assert array.get_object(1) == COSFloat(1.0)
    assert array.get_object(2) == COSFloat(7.0)
    assert array.get_object(3) == COSFloat(8.0)


# ---------- COS surface ----------


def test_get_cos_object_returns_wrapped_array() -> None:
    array = COSArray([COSFloat(0.0), COSFloat(1.0)])
    rng = PDRange(array)
    assert rng.get_cos_object() is array
    assert rng.get_cos_array() is array


# ---------- helpers ----------


def test_width() -> None:
    rng = PDRange()
    assert rng.width() == 1.0
    rng.set_min(-5.0)
    rng.set_max(5.0)
    assert rng.width() == 10.0


def test_contains_inclusive_endpoints() -> None:
    rng = PDRange()
    assert rng.contains(0.0)
    assert rng.contains(1.0)
    assert rng.contains(0.5)
    assert not rng.contains(-0.0001)
    assert not rng.contains(1.0001)


def test_clamp_pulls_to_bounds() -> None:
    rng = PDRange()
    assert rng.clamp(-1.0) == 0.0
    assert rng.clamp(2.0) == 1.0
    assert rng.clamp(0.5) == 0.5


def test_clamp_at_bounds() -> None:
    rng = PDRange()
    assert rng.clamp(0.0) == 0.0
    assert rng.clamp(1.0) == 1.0


def test_is_normalized() -> None:
    assert PDRange().is_normalized()
    rng = PDRange()
    rng.set_max(2.0)
    assert not rng.is_normalized()


def test_is_normalized_accepts_integer_entries() -> None:
    # Even with COSInteger entries, ``[0 1]`` round-trips through
    # float_value() and reads as normalized.
    array = COSArray([COSInteger(0), COSInteger(1)])
    rng = PDRange(array)
    assert rng.is_normalized()


def test_is_well_formed() -> None:
    rng = PDRange()
    assert rng.is_well_formed()
    rng.set_min(2.0)
    rng.set_max(1.0)
    assert not rng.is_well_formed()


def test_iter_yields_min_max_in_order() -> None:
    rng = PDRange()
    rng.set_min(-2.0)
    rng.set_max(2.0)
    lo, hi = rng
    assert lo == -2.0
    assert hi == 2.0


def test_as_tuple() -> None:
    rng = PDRange()
    rng.set_min(-1.5)
    rng.set_max(1.5)
    assert rng.as_tuple() == (-1.5, 1.5)


# ---------- equality / hashing / repr ----------


def test_eq_value_based() -> None:
    a = PDRange()
    b = PDRange()
    assert a == b
    a.set_max(2.0)
    assert a != b


def test_eq_ignores_starting_index_when_values_match() -> None:
    # Two ranges with different backing arrays but identical (min, max)
    # compare equal — equality is over the *values*, not the slot.
    a = PDRange()
    array = COSArray([COSFloat(99.0), COSFloat(99.0), COSFloat(0.0), COSFloat(1.0)])
    b = PDRange(array, 1)
    assert a == b


def test_eq_against_non_pd_range() -> None:
    rng = PDRange()
    assert (rng == (0.0, 1.0)) is False  # NotImplemented → False


def test_hash_matches_equality() -> None:
    a = PDRange()
    b = PDRange()
    assert hash(a) == hash(b)


def test_str_matches_upstream_format() -> None:
    rng = PDRange()
    rng.set_min(0.0)
    rng.set_max(1.0)
    # Upstream toString: "PDRange{0.0, 1.0}".
    assert str(rng) == "PDRange{0.0, 1.0}"


def test_repr_includes_starting_index() -> None:
    array = COSArray(
        [COSFloat(0.0), COSFloat(1.0), COSFloat(2.0), COSFloat(3.0)]
    )
    rng = PDRange(array, 1)
    text = repr(rng)
    assert "starting_index=1" in text
    assert "min=2.0" in text
    assert "max=3.0" in text
