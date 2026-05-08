from __future__ import annotations

from pypdfbox.pdmodel.interactive.annotation.pd_annotation_rubber_stamp import (
    PDAnnotationRubberStamp,
)


def test_rubber_stamp_has_name_distinguishes_implicit_default() -> None:
    implicit = PDAnnotationRubberStamp()
    explicit = PDAnnotationRubberStamp()
    explicit.set_name(PDAnnotationRubberStamp.NAME_DRAFT)

    assert implicit.get_name() == explicit.get_name() == "Draft"
    assert implicit.has_name() is False
    assert explicit.has_name() is True


def test_rubber_stamp_has_name_clears_with_none() -> None:
    ann = PDAnnotationRubberStamp()
    ann.set_name(PDAnnotationRubberStamp.NAME_APPROVED)

    assert ann.has_name() is True

    ann.set_name(None)

    assert ann.has_name() is False
    assert ann.get_name() == PDAnnotationRubberStamp.NAME_DRAFT


def test_rubber_stamp_is_default_name_uses_resolved_name() -> None:
    ann = PDAnnotationRubberStamp()

    assert ann.is_default_name() is True

    ann.set_name(PDAnnotationRubberStamp.NAME_FINAL)
    assert ann.is_default_name() is False

    ann.set_name(PDAnnotationRubberStamp.NAME_DRAFT)
    assert ann.is_default_name() is True
