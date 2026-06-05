from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
    PDAnnotationScreen,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_sound import (
    PDAnnotationSound,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_square_circle import (
    PDAnnotationCircle,
)
from pypdfbox.pdmodel.interactive.annotation.pd_ink_list import PDInkList
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDDestination,
    PDNamedDestination,
    PDPageFitHeightDestination,
    PDPageFitRectangleDestination,
    PDPageFitWidthDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline.pd_outline_item import (
    PDOutlineItem,
)

_AP = COSName.get_pdf_name("AP")
_C = COSName.C  # type: ignore[attr-defined]
_MK = COSName.get_pdf_name("MK")
_SOUND = COSName.get_pdf_name("Sound")


def test_annotation_normal_appearance_stream_none_when_normal_entry_missing() -> None:
    annotation = PDAnnotation()
    annotation.get_cos_object().set_item(_AP, COSDictionary())

    assert annotation.get_normal_appearance_stream() is None


def test_screen_appearance_characteristics_accepts_raw_cos_dictionary() -> None:
    annotation = PDAnnotationScreen()
    raw_mk = COSDictionary()

    annotation.set_appearance_characteristics(raw_mk)

    assert annotation.get_cos_object().get_dictionary_object(_MK) is raw_mk
    assert annotation.get_appearance_characteristics().get_cos_object() is raw_mk


def test_sound_annotation_rejects_non_stream_backed_sound_wrapper() -> None:
    annotation = PDAnnotationSound()

    class NotSoundStream:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

    with pytest.raises(TypeError, match="COSStream-backed"):
        annotation.set_sound(NotSoundStream())  # type: ignore[arg-type]

    assert annotation.get_cos_object().get_dictionary_object(_SOUND) is None


def test_circle_constructor_rejects_non_dictionary_argument() -> None:
    with pytest.raises(TypeError, match="PDAnnotationCircle requires"):
        PDAnnotationCircle("not-a-dictionary")  # type: ignore[arg-type]


def test_ink_list_get_path_rejects_non_array_entry() -> None:
    ink = PDInkList(COSArray([COSString("not-a-path")]))

    with pytest.raises(TypeError, match="expected COSArray"):
        ink.get_path(0)


def test_destination_factory_rejects_unhandled_cos_type() -> None:
    # Mirrors upstream's final else branch ("Error: can't convert to
    # Destination ..."); a bare COSFloat is neither COSArray nor a
    # COSString/COSName named-destination form.
    with pytest.raises(OSError, match="can't convert to Destination"):
        PDDestination.create(COSFloat(1.25))


def test_named_destination_bytes_constructor_decodes_to_string() -> None:
    destination = PDNamedDestination(b"chapter-1")

    assert destination.get_named_destination() == "chapter-1"


def test_fit_height_missing_left_slot_is_unset() -> None:
    destination = PDPageFitHeightDestination(COSArray())

    assert destination.is_left_unset() is True


def test_fit_width_missing_top_slot_is_unset() -> None:
    destination = PDPageFitWidthDestination(COSArray())

    assert destination.is_top_unset() is True


def test_fit_rectangle_missing_coordinate_slot_is_unset() -> None:
    destination = PDPageFitRectangleDestination(COSArray())

    assert destination.is_left_unset() is True


def test_outline_text_color_returns_none_when_component_is_non_numeric() -> None:
    item = PDOutlineItem()
    color = COSArray([COSFloat(1.0), COSName.get_pdf_name("Bad"), COSFloat(0.0)])
    item.get_cos_object().set_item(_C, color)

    assert item.get_text_color() is None
