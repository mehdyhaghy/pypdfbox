from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fdf import (
    FDFAnnotation,
    FDFAnnotationHighlight,
    FDFAnnotationTextMarkup,
)


def test_default_constructor_sets_subtype() -> None:
    annot = FDFAnnotationHighlight()
    assert annot.get_cos_object().get_name_as_string("Subtype") == "Highlight"


def test_is_text_markup_subclass() -> None:
    assert issubclass(FDFAnnotationHighlight, FDFAnnotationTextMarkup)
    assert isinstance(FDFAnnotationHighlight(), FDFAnnotationTextMarkup)


def test_coords_roundtrip() -> None:
    annot = FDFAnnotationHighlight()
    coords = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    annot.set_coords(coords)
    assert annot.get_coords() == pytest.approx(coords)


def test_coords_default_none() -> None:
    assert FDFAnnotationHighlight().get_coords() is None


def test_existing_dict_keeps_subtype() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Highlight")
    annot = FDFAnnotationHighlight(src)
    assert annot.get_cos_object() is src
    assert annot.get_subtype() == "Highlight"


def test_create_dispatches_to_highlight() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Highlight")
    assert isinstance(FDFAnnotation.create(src), FDFAnnotationHighlight)
