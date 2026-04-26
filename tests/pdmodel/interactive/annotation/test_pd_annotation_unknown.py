from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.annotation import (
    PDAnnotation,
    PDAnnotationUnknown,
)


def test_unknown_wraps_dict() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "FreeText")  # type: ignore[attr-defined]
    ann = PDAnnotationUnknown(d)
    assert ann.get_cos_object() is d
    assert ann.get_subtype() == "FreeText"


def test_unknown_with_no_subtype() -> None:
    d = COSDictionary()
    ann = PDAnnotationUnknown(d)
    assert ann.get_subtype() is None


def test_unknown_inherits_base_accessors() -> None:
    d = COSDictionary()
    ann = PDAnnotationUnknown(d)
    ann.set_contents("anything")
    assert ann.get_contents() == "anything"
    ann.set_annotation_name("nm-1")
    assert ann.get_annotation_name() == "nm-1"


def test_unknown_is_pdannotation() -> None:
    d = COSDictionary()
    assert isinstance(PDAnnotationUnknown(d), PDAnnotation)
