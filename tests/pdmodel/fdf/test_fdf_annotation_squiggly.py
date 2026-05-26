from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fdf import (
    FDFAnnotation,
    FDFAnnotationSquiggly,
    FDFAnnotationTextMarkup,
)


def test_default_constructor_sets_subtype() -> None:
    annot = FDFAnnotationSquiggly()
    assert annot.get_cos_object().get_name_as_string("Subtype") == "Squiggly"


def test_is_text_markup_subclass() -> None:
    assert issubclass(FDFAnnotationSquiggly, FDFAnnotationTextMarkup)
    assert isinstance(FDFAnnotationSquiggly(), FDFAnnotationTextMarkup)


def test_coords_roundtrip() -> None:
    annot = FDFAnnotationSquiggly()
    coords = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
    annot.set_coords(coords)
    assert annot.get_coords() == pytest.approx(coords)


def test_existing_dict_keeps_subtype() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Squiggly")
    annot = FDFAnnotationSquiggly(src)
    assert annot.get_cos_object() is src
    assert annot.get_subtype() == "Squiggly"


def test_create_dispatches_to_squiggly() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Squiggly")
    assert isinstance(FDFAnnotation.create(src), FDFAnnotationSquiggly)
