"""Defensive-copy parity for ``PDVisibleSignDesigner.transform`` (wave 1503).

Upstream ``transform(AffineTransform)`` stores ``new AffineTransform(at)`` —
a defensive copy — so a later mutation of the caller's transform cannot leak
into the designer (PDVisibleSignDesigner.java line 477). The Python port
reproduces this in three tiers:

  1. component snapshot for any conforming transform (the rotation path and
     any object exposing ``m00..m12``),
  2. ``copy.copy`` for other copyable objects,
  3. by-reference for uncopyable opaque handles (documented residual).

These tests pin all three tiers plus the mutation-isolation contract that is
the whole point of upstream's defensive copy.
"""

from __future__ import annotations

import copy

import pytest

from pypdfbox.pdmodel.interactive.digitalsignature.visible.pd_visible_sign_designer import (
    PDVisibleSignDesigner,
    _copy_affine_transform,
    _IdentityAffineTransform,
)


# ---------------------------------------------------------------------------
# tier 1: conforming affine-transform component snapshot
# ---------------------------------------------------------------------------
def test_transform_snapshots_conforming_components_into_fresh_instance() -> None:
    supplied = _IdentityAffineTransform(2.0, 1.0, -1.0, 3.0, 5.0, 7.0)
    designer = PDVisibleSignDesigner()
    designer.transform(supplied)
    stored = designer.get_transform()

    assert stored is not supplied
    assert isinstance(stored, _IdentityAffineTransform)
    assert (
        stored.m00, stored.m10, stored.m01, stored.m11, stored.m02, stored.m12
    ) == (2.0, 1.0, -1.0, 3.0, 5.0, 7.0)


def test_transform_copy_is_isolated_from_caller_mutation() -> None:
    """The defensive-copy contract: mutating the caller's transform after
    the ``transform()`` call must not change the stored matrix."""
    supplied = _IdentityAffineTransform(1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    designer = PDVisibleSignDesigner()
    designer.transform(supplied)

    supplied.m00 = 99.0
    supplied.m02 = 42.0

    stored = designer.get_transform()
    assert stored.m00 == 1.0
    assert stored.m02 == 0.0


def test_transform_accepts_duck_typed_affine_with_all_six_components() -> None:
    class _DuckAffine:
        m00 = 4.0
        m10 = 0.0
        m01 = 0.0
        m11 = 5.0
        m02 = 6.0
        m12 = 8.0

    designer = PDVisibleSignDesigner()
    designer.transform(_DuckAffine())
    stored = designer.get_transform()
    assert isinstance(stored, _IdentityAffineTransform)
    assert (stored.m00, stored.m11, stored.m02, stored.m12) == (4.0, 5.0, 6.0, 8.0)


# ---------------------------------------------------------------------------
# tier 2: copy.copy fallback for non-conforming but copyable objects
# ---------------------------------------------------------------------------
def test_transform_shallow_copies_non_conforming_copyable_object() -> None:
    class _OtherTransform:
        def __init__(self) -> None:
            self.value = 11

    supplied = _OtherTransform()
    designer = PDVisibleSignDesigner()
    designer.transform(supplied)
    stored = designer.get_transform()

    assert stored is not supplied
    assert isinstance(stored, _OtherTransform)
    assert stored.value == 11


def test_transform_partial_affine_components_falls_to_copy() -> None:
    # Missing m12 -> not a conforming affine, so it goes through copy.copy.
    class _PartialAffine:
        m00 = 1.0
        m10 = 0.0
        m01 = 0.0
        m11 = 1.0
        m02 = 0.0

    supplied = _PartialAffine()
    designer = PDVisibleSignDesigner()
    designer.transform(supplied)
    stored = designer.get_transform()
    assert stored is not supplied
    assert isinstance(stored, _PartialAffine)


# ---------------------------------------------------------------------------
# tier 3: uncopyable opaque handle stored by reference
# ---------------------------------------------------------------------------
def test_transform_uncopyable_object_stored_by_reference() -> None:
    class _Opaque:
        def __copy__(self) -> _Opaque:
            raise TypeError("cannot copy opaque handle")

    supplied = _Opaque()
    designer = PDVisibleSignDesigner()
    designer.transform(supplied)
    # No conforming components, copy raises -> by-reference residual.
    assert designer.get_transform() is supplied


def test_transform_returns_self_for_chaining() -> None:
    designer = PDVisibleSignDesigner()
    result = designer.transform(_IdentityAffineTransform())
    assert result is designer


# ---------------------------------------------------------------------------
# helper-level coverage
# ---------------------------------------------------------------------------
def test_copy_affine_transform_none_passthrough() -> None:
    assert _copy_affine_transform(None) is None


def test_copy_affine_transform_matches_copy_module_for_plain_object() -> None:
    class _Plain:
        x = 1

    src = _Plain()
    out = _copy_affine_transform(src)
    assert out is not src
    assert isinstance(out, _Plain)
    # Mirrors copy.copy semantics for a non-affine object.
    assert isinstance(copy.copy(src), _Plain)


# ---------------------------------------------------------------------------
# the rotation path still produces fresh, independent transforms
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_rotation_transform_is_fresh_identity_instance(rotation: int) -> None:
    designer = PDVisibleSignDesigner()
    designer.page_width(600.0).page_height(800.0)
    designer.width(100.0).height(40.0).coordinates(10.0, 20.0)
    designer._rotation = rotation
    designer.adjust_for_rotation()
    transform = designer.get_transform()
    assert isinstance(transform, _IdentityAffineTransform)
    # Adjusting again from a different designer must not share state.
    other = PDVisibleSignDesigner()
    other._rotation = rotation
    other.page_width(600.0).page_height(800.0)
    other.width(100.0).height(40.0).coordinates(10.0, 20.0)
    other.adjust_for_rotation()
    assert other.get_transform() is not transform
