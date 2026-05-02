from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCircle,
    PDAnnotationSquare,
    PDAnnotationSquareCircle,
)
from pypdfbox.pdmodel.pd_rectangle import PDRectangle


def test_square_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationSquare()
    assert ann.get_subtype() == "Square"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_circle_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationCircle()
    assert ann.get_subtype() == "Circle"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_square_subtype_constant() -> None:
    assert PDAnnotationSquare.SUB_TYPE == "Square"


def test_circle_subtype_constant() -> None:
    assert PDAnnotationCircle.SUB_TYPE == "Circle"


def test_square_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Square")  # type: ignore[attr-defined]
    ann = PDAnnotationSquare(d)
    assert ann.get_subtype() == "Square"
    assert ann.get_cos_object() is d


def test_circle_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Circle")  # type: ignore[attr-defined]
    ann = PDAnnotationCircle(d)
    assert ann.get_subtype() == "Circle"
    assert ann.get_cos_object() is d


def test_square_and_circle_share_base() -> None:
    assert issubclass(PDAnnotationSquare, PDAnnotationSquareCircle)
    assert issubclass(PDAnnotationCircle, PDAnnotationSquareCircle)


def test_border_style_round_trip_square() -> None:
    from pypdfbox.pdmodel.interactive.annotation import PDBorderStyleDictionary

    ann = PDAnnotationSquare()
    bs = COSDictionary()
    bs.set_int(COSName.get_pdf_name("W"), 3)
    ann.set_border_style(bs)
    resolved = ann.get_border_style()
    assert isinstance(resolved, PDBorderStyleDictionary)
    assert resolved.get_cos_object() is bs


def test_border_style_round_trip_circle() -> None:
    from pypdfbox.pdmodel.interactive.annotation import PDBorderStyleDictionary

    ann = PDAnnotationCircle()
    bs = COSDictionary()
    bs.set_int(COSName.get_pdf_name("W"), 3)
    ann.set_border_style(bs)
    resolved = ann.get_border_style()
    assert isinstance(resolved, PDBorderStyleDictionary)
    assert resolved.get_cos_object() is bs


def test_border_style_default_none() -> None:
    ann = PDAnnotationSquare()
    assert ann.get_border_style() is None


def test_border_style_clear() -> None:
    ann = PDAnnotationSquare()
    ann.set_border_style(COSDictionary())
    ann.set_border_style(None)
    assert ann.get_border_style() is None


def test_interior_color_round_trip() -> None:
    ann = PDAnnotationSquare()
    ic = COSArray([COSFloat(1.0), COSFloat(1.0), COSFloat(0.0)])
    ann.set_interior_color(ic)
    assert ann.get_interior_color() is ic


def test_interior_color_default_none() -> None:
    ann = PDAnnotationCircle()
    assert ann.get_interior_color() is None


def test_interior_color_clear() -> None:
    ann = PDAnnotationCircle()
    ann.set_interior_color(COSArray([COSFloat(0.0)]))
    ann.set_interior_color(None)
    assert ann.get_interior_color() is None


def test_border_effect_round_trip() -> None:
    ann = PDAnnotationSquare()
    be = COSDictionary()
    be.set_name(COSName.get_pdf_name("S"), "C")
    ann.set_border_effect(be)
    assert ann.get_border_effect() is be


def test_border_effect_default_none() -> None:
    ann = PDAnnotationCircle()
    assert ann.get_border_effect() is None


def test_border_effect_clear() -> None:
    ann = PDAnnotationCircle()
    ann.set_border_effect(COSDictionary())
    ann.set_border_effect(None)
    assert ann.get_border_effect() is None


# ---------- /RD (rectangle difference) ----------


def test_rect_difference_default_is_none() -> None:
    ann = PDAnnotationSquare()
    assert ann.get_rect_difference() is None


def test_rect_differences_default_is_empty_list() -> None:
    """Mirror upstream's ``new float[]{}`` default for ``getRectDifferences``."""
    ann = PDAnnotationCircle()
    assert ann.get_rect_differences() == []


def test_set_rect_difference_round_trip_square() -> None:
    ann = PDAnnotationSquare()
    rect = PDRectangle(1.0, 2.0, 3.0, 4.0)
    ann.set_rect_difference(rect)
    resolved = ann.get_rect_difference()
    assert resolved is not None
    assert resolved == rect


def test_set_rect_difference_round_trip_circle() -> None:
    ann = PDAnnotationCircle()
    rect = PDRectangle(0.5, 1.5, 2.5, 3.5)
    ann.set_rect_difference(rect)
    resolved = ann.get_rect_difference()
    assert resolved is not None
    assert resolved == rect


def test_set_rect_difference_none_clears() -> None:
    ann = PDAnnotationSquare()
    ann.set_rect_difference(PDRectangle(0, 0, 1, 1))
    ann.set_rect_difference(None)
    assert ann.get_rect_difference() is None
    assert ann.get_rect_differences() == []


def test_get_rect_difference_short_array_returns_none() -> None:
    """Fewer than 4 entries → ``None`` per upstream guard."""
    ann = PDAnnotationCircle()
    short = COSArray([COSFloat(1.0), COSFloat(2.0)])
    ann.get_cos_object().set_item(COSName.get_pdf_name("RD"), short)
    assert ann.get_rect_difference() is None


def test_set_rect_differences_uniform_single_float() -> None:
    """``set_rect_differences(d)`` → all four sides equal ``d``."""
    ann = PDAnnotationSquare()
    ann.set_rect_differences(2.5)
    assert ann.get_rect_differences() == [2.5, 2.5, 2.5, 2.5]


def test_set_rect_differences_four_values() -> None:
    ann = PDAnnotationCircle()
    ann.set_rect_differences(1.0, 2.0, 3.0, 4.0)
    assert ann.get_rect_differences() == [1.0, 2.0, 3.0, 4.0]


def test_set_rect_differences_list_form() -> None:
    ann = PDAnnotationSquare()
    ann.set_rect_differences([5.0, 6.0, 7.0, 8.0])
    assert ann.get_rect_differences() == [5.0, 6.0, 7.0, 8.0]


def test_set_rect_differences_none_clears() -> None:
    ann = PDAnnotationCircle()
    ann.set_rect_differences(3.0)
    ann.set_rect_differences(None)
    assert ann.get_rect_differences() == []
    assert ann.get_rect_difference() is None


def test_set_rect_differences_list_wrong_length_raises() -> None:
    ann = PDAnnotationSquare()
    with pytest.raises(ValueError):
        ann.set_rect_differences([1.0, 2.0])


def test_set_rect_differences_invalid_arity_raises() -> None:
    ann = PDAnnotationCircle()
    with pytest.raises(TypeError):
        ann.set_rect_differences(1.0, 2.0, 3.0)  # type: ignore[arg-type]


def test_get_rect_differences_after_set_rect_difference() -> None:
    """Singular ``set_rect_difference`` round-trips through plural getter."""
    ann = PDAnnotationSquare()
    ann.set_rect_difference(PDRectangle(0.0, 0.0, 4.0, 8.0))
    diffs = ann.get_rect_differences()
    assert len(diffs) == 4
    # PDRectangle.to_cos_array emits [llx, lly, urx, ury]
    assert diffs == [0.0, 0.0, 4.0, 8.0]
