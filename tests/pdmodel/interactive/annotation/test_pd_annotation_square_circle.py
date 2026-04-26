from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotationCircle,
    PDAnnotationSquare,
    PDAnnotationSquareCircle,
)


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
