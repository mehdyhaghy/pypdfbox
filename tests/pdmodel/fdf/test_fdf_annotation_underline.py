from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary
from pypdfbox.pdmodel.fdf import (
    FDFAnnotation,
    FDFAnnotationTextMarkup,
    FDFAnnotationUnderline,
)


def test_default_constructor_sets_subtype() -> None:
    annot = FDFAnnotationUnderline()
    assert annot.get_cos_object().get_name_as_string("Subtype") == "Underline"


def test_is_text_markup_subclass() -> None:
    assert issubclass(FDFAnnotationUnderline, FDFAnnotationTextMarkup)
    assert isinstance(FDFAnnotationUnderline(), FDFAnnotationTextMarkup)


def test_coords_roundtrip() -> None:
    annot = FDFAnnotationUnderline()
    coords = [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0]
    annot.set_coords(coords)
    assert annot.get_coords() == pytest.approx(coords)


def test_coords_clear() -> None:
    annot = FDFAnnotationUnderline()
    annot.set_coords([0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0])
    annot.set_coords(None)
    assert annot.get_coords() is None


def test_existing_dict_keeps_subtype() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Underline")
    annot = FDFAnnotationUnderline(src)
    assert annot.get_cos_object() is src
    assert annot.get_subtype() == "Underline"


def test_create_dispatches_to_underline() -> None:
    src = COSDictionary()
    src.set_name("Subtype", "Underline")
    assert isinstance(FDFAnnotation.create(src), FDFAnnotationUnderline)
