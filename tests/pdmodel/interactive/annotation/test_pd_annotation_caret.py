from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_caret import (
    PDAnnotationCaret,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)


def test_caret_subtype_constant() -> None:
    assert PDAnnotationCaret.SUB_TYPE == "Caret"


def test_caret_inherits_markup() -> None:
    assert issubclass(PDAnnotationCaret, PDAnnotationMarkup)


def test_caret_default_constructor_sets_type_and_subtype() -> None:
    ann = PDAnnotationCaret()
    cos = ann.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]
    assert ann.get_subtype() == "Caret"


def test_caret_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Caret")  # type: ignore[attr-defined]
    ann = PDAnnotationCaret(d)
    assert ann.get_subtype() == "Caret"
    assert ann.get_cos_object() is d


def test_caret_inherits_markup_subject() -> None:
    ann = PDAnnotationCaret()
    ann.set_subject("Insert here")
    assert ann.get_subject() == "Insert here"


def test_caret_rectangle_difference_aliases_round_trip_and_clear() -> None:
    ann = PDAnnotationCaret()

    ann.set_rect_differences([1, 2.5, 3, 4])

    assert ann.get_rectangle_differences() == [1.0, 2.5, 3.0, 4.0]
    assert ann.get_rect_differences() == [1.0, 2.5, 3.0, 4.0]

    ann.set_rect_differences(None)
    assert ann.get_rectangle_differences() is None


def test_caret_rectangle_difference_alias_rejects_wrong_length() -> None:
    ann = PDAnnotationCaret()

    with pytest.raises(ValueError):
        ann.set_rect_differences([1, 2, 3])


def test_caret_factory_dispatch() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Caret")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationCaret)
    assert ann.get_subtype() == "Caret"
