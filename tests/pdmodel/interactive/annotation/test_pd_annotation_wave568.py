from __future__ import annotations

import datetime as dt

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotation, PDAnnotationText
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_unknown import (
    PDAnnotationUnknown,
)


def test_wave568_constructor_adds_missing_type_but_preserves_existing_type() -> None:
    missing_type = COSDictionary()
    annotation = PDAnnotation(missing_type)

    assert annotation.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]

    existing_type = COSDictionary()
    existing_type.set_item(COSName.TYPE, COSName.get_pdf_name("Custom"))  # type: ignore[attr-defined]
    annotation = PDAnnotation(existing_type)

    assert annotation.get_cos_object().get_name(COSName.TYPE) == "Custom"  # type: ignore[attr-defined]


def test_wave568_create_missing_subtype_returns_unknown_with_type_defaulted() -> None:
    raw = COSDictionary()

    annotation = PDAnnotation.create(raw)

    assert isinstance(annotation, PDAnnotationUnknown)
    assert annotation.get_subtype() is None
    assert raw.get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    ("flag", "setter_name", "getter_name"),
    [
        (PDAnnotation.FLAG_INVISIBLE, "set_invisible", "is_invisible"),
        (PDAnnotation.FLAG_HIDDEN, "set_hidden", "is_hidden"),
        (PDAnnotation.FLAG_NO_ZOOM, "set_no_zoom", "is_no_zoom"),
        (PDAnnotation.FLAG_NO_ROTATE, "set_no_rotate", "is_no_rotate"),
        (PDAnnotation.FLAG_NO_VIEW, "set_no_view", "is_no_view"),
        (PDAnnotation.FLAG_READ_ONLY, "set_read_only", "is_read_only"),
        (PDAnnotation.FLAG_TOGGLE_NO_VIEW, "set_toggle_no_view", "is_toggle_no_view"),
        (PDAnnotation.FLAG_LOCKED_CONTENTS, "set_locked_contents", "is_locked_contents"),
    ],
)
def test_wave568_each_annotation_flag_toggles_only_its_bit(
    flag: int, setter_name: str, getter_name: str
) -> None:
    annotation = PDAnnotationText()
    setter = getattr(annotation, setter_name)
    getter = getattr(annotation, getter_name)

    setter(True)
    assert getter() is True
    assert annotation.get_annotation_flags() == flag

    setter(False)
    assert getter() is False
    assert annotation.get_annotation_flags() == 0


def test_wave568_annotation_name_title_and_modified_date_clear() -> None:
    annotation = PDAnnotationText()
    annotation.set_annotation_name("annot-1")
    annotation.set_title_popup("Reviewer")
    annotation.set_modified_date(dt.datetime(2024, 1, 2, 3, 4, 5))

    assert annotation.get_annotation_name() == "annot-1"
    assert annotation.get_title_popup() == "Reviewer"
    # Upstream DateConverter.toString renders UTC as +00'00', never Z.
    assert annotation.get_modified_date() == "D:20240102030405+00'00'"

    annotation.set_annotation_name(None)
    annotation.set_title_popup(None)
    annotation.set_modified_date(None)

    assert annotation.get_annotation_name() is None
    assert annotation.get_title_popup() is None
    assert annotation.get_modified_date() is None


def test_wave568_set_color_components_and_clear_appearance_state() -> None:
    annotation = PDAnnotationText()

    annotation.set_color_components((0.25, 0.5, 0.75))
    color = annotation.get_color()

    assert color is not None
    assert [color.get(i).value for i in range(color.size())] == [0.25, 0.5, 0.75]

    annotation.set_appearance_state(COSName.get_pdf_name("On"))
    assert annotation.get_appearance_state() == "On"

    annotation.set_appearance_state(None)
    assert annotation.get_appearance_state() is None


def test_wave568_malformed_parent_page_reads_absent_and_set_p_clears() -> None:
    annotation = PDAnnotationText()
    annotation.get_cos_object().set_item(COSName.get_pdf_name("P"), COSString("bad"))

    assert annotation.get_p() is None
    assert annotation.get_page() is None

    page = COSDictionary()
    annotation.set_page(page)
    assert annotation.get_p() is page

    annotation.set_p(None)
    assert annotation.get_p() is None

