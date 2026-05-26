from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fdf import (
    FDFAnnotation,
    FDFAnnotationStrikeOut,
    FDFAnnotationTextMarkup,
)


def test_default_constructor_sets_subtype() -> None:
    annot = FDFAnnotationStrikeOut()
    assert annot.get_cos_object().get_name_as_string("Subtype") == "StrikeOut"


def test_is_text_markup_subclass() -> None:
    assert issubclass(FDFAnnotationStrikeOut, FDFAnnotationTextMarkup)
    assert isinstance(FDFAnnotationStrikeOut(), FDFAnnotationTextMarkup)


def test_coords_roundtrip() -> None:
    annot = FDFAnnotationStrikeOut()
    coords = [1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5, 8.5]
    annot.set_coords(coords)
    assert annot.get_coords() == pytest.approx(coords)


def test_existing_dict_keeps_subtype() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "StrikeOut")
    annot = FDFAnnotationStrikeOut(src)
    assert annot.get_cos_object() is src
    assert annot.get_subtype() == "StrikeOut"


def test_create_dispatches_to_strike_out() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "StrikeOut")
    assert isinstance(FDFAnnotation.create(src), FDFAnnotationStrikeOut)
