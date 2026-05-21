"""Deep parity tests for ``PDAbstractPattern``. Mirrors upstream
``pdfbox/src/main/java/org/apache/pdfbox/pdmodel/graphics/pattern/PDAbstractPattern.java``.

Existing coverage in ``test_pattern_parity.py`` covers the predicate
surface; the cases below pin:

  * Factory ``create()`` with ``resource_cache`` argument (mirrors
    upstream's two-arg overload).
  * ``/Matrix`` setter accepting an AffineTransform-like adapter
    (upstream's ``setMatrix(AffineTransform)`` shape).
  * ``/Matrix`` permissive parsing (missing / short / non-numeric entries
    fall back to identity per ``Matrix.createMatrix`` semantics).
  * ``set_pattern_type`` / ``set_paint_type`` setters (upstream parity).
  * Untyped ``get_pattern_type`` raises ``NotImplementedError`` on the
    base class only.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
)
from pypdfbox.pdmodel.graphics.pattern import (
    PDAbstractPattern,
    PDShadingPattern,
    PDTilingPattern,
)

# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def test_create_with_resource_cache_argument_accepts_none():
    """Upstream ``PDAbstractPattern.create(COSDictionary, ResourceCache)``
    accepts the cache argument; with ``None`` the dispatch still returns
    the right subclass."""
    d = COSDictionary()
    d.set_int("PatternType", 1)
    result = PDAbstractPattern.create(d, resource_cache=None)
    assert isinstance(result, PDTilingPattern)


def test_create_returns_none_for_none_dictionary():
    assert PDAbstractPattern.create(None) is None


def test_create_rejects_non_dictionary_typeerror():
    with pytest.raises(TypeError):
        PDAbstractPattern.create(COSArray())  # type: ignore[arg-type]


def test_create_rejects_unknown_pattern_type():
    d = COSDictionary()
    d.set_int("PatternType", 99)
    with pytest.raises(OSError):
        PDAbstractPattern.create(d)


def test_create_rejects_zero_pattern_type():
    # Missing /PatternType (defaults to 0) → unknown type.
    d = COSDictionary()
    with pytest.raises(OSError):
        PDAbstractPattern.create(d)


def test_create_dispatches_type1_returns_tiling():
    d = COSDictionary()
    d.set_int("PatternType", 1)
    result = PDAbstractPattern.create(d)
    assert isinstance(result, PDTilingPattern)
    assert result.get_pattern_type() == 1


def test_create_dispatches_type2_returns_shading():
    d = COSDictionary()
    d.set_int("PatternType", 2)
    result = PDAbstractPattern.create(d)
    assert isinstance(result, PDShadingPattern)
    assert result.get_pattern_type() == 2


# ---------------------------------------------------------------------------
# Abstract base raises on get_pattern_type when /PatternType absent
# ---------------------------------------------------------------------------


def test_base_get_pattern_type_raises_when_no_entry():
    base = PDAbstractPattern(COSDictionary())  # bypass fresh-init defaulting
    # Remove the /Type entry our base would have set, no /PatternType present.
    base.get_cos_object().remove_item(COSName.get_pdf_name("PatternType"))
    with pytest.raises(NotImplementedError):
        base.get_pattern_type()


def test_base_get_pattern_type_falls_back_to_stored_value():
    """The base class's ``get_pattern_type`` returns the stored
    ``/PatternType`` value when it's set, even on a bare ``PDAbstractPattern``
    instance — useful for stub / introspection callers."""
    base = PDAbstractPattern(COSDictionary())
    base.get_cos_object().set_int("PatternType", 1)
    assert base.get_pattern_type() == 1
    base.get_cos_object().set_int("PatternType", 2)
    assert base.get_pattern_type() == 2


def test_set_pattern_type_round_trip():
    base = PDAbstractPattern(COSDictionary())
    base.set_pattern_type(2)
    assert base.get_cos_object().get_int("PatternType") == 2


def test_set_paint_type_round_trip_on_base():
    base = PDAbstractPattern(COSDictionary())
    base.set_paint_type(2)
    assert base.get_cos_object().get_int("PaintType") == 2


# ---------------------------------------------------------------------------
# /Matrix accessors
# ---------------------------------------------------------------------------


def test_get_matrix_default_is_identity():
    pattern = PDShadingPattern()
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    # No /Matrix entry written for the default — only on explicit set.
    assert pattern.has_matrix() is False


def test_set_matrix_with_list_round_trips():
    pattern = PDShadingPattern()
    pattern.set_matrix([1.5, 0.0, 0.0, 2.5, 5.0, 7.0])
    assert pattern.get_matrix() == [1.5, 0.0, 0.0, 2.5, 5.0, 7.0]
    assert pattern.has_matrix() is True


def test_set_matrix_with_tuple_round_trips():
    pattern = PDShadingPattern()
    pattern.set_matrix((2.0, 0.0, 0.0, 3.0, 10.0, 20.0))
    assert pattern.get_matrix() == [2.0, 0.0, 0.0, 3.0, 10.0, 20.0]


def test_set_matrix_with_none_clears_entry():
    pattern = PDShadingPattern()
    pattern.set_matrix([1.5, 0.0, 0.0, 2.5, 5.0, 7.0])
    pattern.set_matrix(None)
    assert pattern.has_matrix() is False
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_set_matrix_rejects_wrong_length():
    pattern = PDShadingPattern()
    with pytest.raises(ValueError):
        pattern.set_matrix([1.0, 0.0, 0.0, 1.0, 0.0])  # 5 elements
    with pytest.raises(ValueError):
        pattern.set_matrix([1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 999.0])  # 7 elements


def test_set_matrix_accepts_affine_transform_like_adapter():
    """Upstream ``setMatrix(AffineTransform)`` reads 6 entries via
    ``transform.getMatrix(double[])``. The Python port duck-types — any
    object with a callable ``get_matrix()`` returning 6 values works."""

    class Affine:
        def get_matrix(self):
            return [2.0, 0.0, 0.0, 2.0, 100.0, 200.0]

    pattern = PDShadingPattern()
    pattern.set_matrix(Affine())
    assert pattern.get_matrix() == [2.0, 0.0, 0.0, 2.0, 100.0, 200.0]


def test_set_matrix_affine_transform_wrong_length_raises():
    class BadAffine:
        def get_matrix(self):
            return [1.0, 0.0, 0.0]  # too short

    pattern = PDShadingPattern()
    with pytest.raises(ValueError):
        pattern.set_matrix(BadAffine())


def test_get_matrix_falls_back_to_identity_for_short_array():
    """``Matrix.createMatrix`` upstream returns identity on short arrays —
    our wrapper matches by returning ``[1, 0, 0, 1, 0, 0]`` rather than
    raising."""
    pattern = PDShadingPattern()
    short = COSArray()
    for v in (1.0, 0.0, 0.0):  # only 3 entries
        short.add(COSFloat(v))
    pattern.get_cos_object().set_item(COSName.get_pdf_name("Matrix"), short)
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]
    assert pattern.has_matrix() is False  # malformed → not "has"


def test_get_matrix_falls_back_to_identity_for_non_numeric_entry():
    pattern = PDShadingPattern()
    bad = COSArray()
    bad.add(COSFloat(1.0))
    bad.add(COSName.get_pdf_name("Bogus"))
    bad.add(COSFloat(0.0))
    bad.add(COSFloat(1.0))
    bad.add(COSFloat(0.0))
    bad.add(COSFloat(0.0))
    pattern.get_cos_object().set_item(COSName.get_pdf_name("Matrix"), bad)
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_get_matrix_falls_back_to_identity_for_non_array():
    pattern = PDShadingPattern()
    pattern.get_cos_object().set_item(
        COSName.get_pdf_name("Matrix"), COSInteger.get(5)
    )
    assert pattern.get_matrix() == [1.0, 0.0, 0.0, 1.0, 0.0, 0.0]


def test_has_matrix_true_only_for_valid_six_element_array():
    pattern = PDShadingPattern()
    pattern.set_matrix([1.0, 0.0, 0.0, 1.0, 0.0, 0.0])
    assert pattern.has_matrix() is True
    pattern.clear_matrix()
    assert pattern.has_matrix() is False


def test_clear_matrix_is_noop_when_absent():
    pattern = PDShadingPattern()
    pattern.clear_matrix()
    assert pattern.has_matrix() is False


# ---------------------------------------------------------------------------
# /ExtGState surface on the abstract base (back-compat raw accessor)
# ---------------------------------------------------------------------------


def test_base_get_extended_graphics_state_returns_raw_dict():
    pattern = PDTilingPattern()
    ext = COSDictionary()
    ext.set_int("Foo", 5)
    pattern.set_extended_graphics_state(ext)
    got = pattern.get_extended_graphics_state()
    # Base accessor returns the raw COSDictionary (not a wrapper).
    assert got is ext


def test_base_get_ext_g_state_returns_typed_wrapper():
    from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
        PDExtendedGraphicsState,
    )

    pattern = PDTilingPattern()
    pattern.set_ext_g_state(PDExtendedGraphicsState())
    got = pattern.get_ext_g_state()
    assert isinstance(got, PDExtendedGraphicsState)


# ---------------------------------------------------------------------------
# Type predicates on the abstract surface
# ---------------------------------------------------------------------------


def test_is_tiling_pattern_only_for_type_1():
    tiling = PDTilingPattern()
    shading = PDShadingPattern()
    assert tiling.is_tiling_pattern() is True
    assert tiling.is_shading_pattern() is False
    assert shading.is_tiling_pattern() is False
    assert shading.is_shading_pattern() is True


def test_get_type_always_returns_pattern():
    assert PDTilingPattern().get_type() == "Pattern"
    assert PDShadingPattern().get_type() == "Pattern"
