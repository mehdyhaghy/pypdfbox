from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_ink import (
    PDAnnotationInk,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
    PDAnnotationMarkup,
)
from pypdfbox.pdmodel.interactive.annotation.pd_ink_list import PDInkList
from pypdfbox.pdmodel.interactive.annotation.pd_path_info import PDPathInfo


def _make_path(points: list[float]) -> PDPathInfo:
    arr = COSArray([COSFloat(float(p)) for p in points])
    return PDPathInfo(arr)


def test_ink_subtype_constant() -> None:
    assert PDAnnotationInk.SUB_TYPE == "Ink"


def test_ink_inherits_markup() -> None:
    assert issubclass(PDAnnotationInk, PDAnnotationMarkup)


def test_ink_default_constructor_sets_type_and_subtype() -> None:
    ann = PDAnnotationInk()
    cos = ann.get_cos_object()
    assert cos.get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]
    assert ann.get_subtype() == "Ink"


def test_ink_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Ink")  # type: ignore[attr-defined]
    ann = PDAnnotationInk(d)
    assert ann.get_subtype() == "Ink"
    assert ann.get_cos_object() is d


def test_ink_get_ink_list_default_none() -> None:
    ann = PDAnnotationInk()
    assert ann.get_ink_list() is None


def test_ink_set_ink_list_round_trip() -> None:
    ann = PDAnnotationInk()
    ink = PDInkList()
    ink.add_path(_make_path([10.0, 20.0, 30.0, 40.0]))
    ink.add_path(_make_path([50.0, 60.0, 70.0, 80.0, 90.0, 100.0]))
    ann.set_ink_list(ink)
    fetched = ann.get_ink_list()
    assert fetched is not None
    assert fetched.path_count() == 2


def test_ink_set_ink_list_accepts_raw_cos_array() -> None:
    ann = PDAnnotationInk()
    raw = COSArray()
    raw.add(COSArray([COSFloat(1.0), COSFloat(2.0), COSFloat(3.0), COSFloat(4.0)]))
    ann.set_ink_list(raw)
    fetched = ann.get_ink_list()
    assert fetched is not None
    assert fetched.path_count() == 1


def test_ink_set_ink_list_none_clears() -> None:
    ann = PDAnnotationInk()
    ink = PDInkList()
    ink.add_path(_make_path([0.0, 0.0, 1.0, 1.0]))
    ann.set_ink_list(ink)
    ann.set_ink_list(None)
    assert ann.get_ink_list() is None


def test_ink_inherits_markup_subject() -> None:
    ann = PDAnnotationInk()
    ann.set_subject("Hand-drawn note")
    assert ann.get_subject() == "Hand-drawn note"


def test_ink_factory_dispatch() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Ink")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationInk)
    assert ann.get_subtype() == "Ink"
