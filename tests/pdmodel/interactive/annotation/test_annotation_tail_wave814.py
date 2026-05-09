from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
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

_A = COSName.get_pdf_name("A")
_AP = COSName.get_pdf_name("AP")
_SOUND = COSName.get_pdf_name("Sound")


def test_annotation_normal_appearance_stream_none_when_normal_slot_absent() -> None:
    annotation = PDAnnotation()
    annotation.get_cos_object().set_item(_AP, COSDictionary())

    assert annotation.get_normal_appearance_stream() is None


def test_screen_action_accepts_raw_cos_dictionary() -> None:
    annotation = PDAnnotationScreen()
    raw_action = COSDictionary()

    annotation.set_action(raw_action)

    assert annotation.get_cos_object().get_dictionary_object(_A) is raw_action


def test_sound_annotation_rejects_wrapper_without_sound_stream() -> None:
    annotation = PDAnnotationSound()

    class DictionaryBackedSound:
        def get_cos_object(self) -> COSDictionary:
            return COSDictionary()

    with pytest.raises(TypeError, match="COSStream-backed"):
        annotation.set_sound(DictionaryBackedSound())  # type: ignore[arg-type]

    assert annotation.get_cos_object().get_dictionary_object(_SOUND) is None


def test_circle_constructor_rejects_non_dictionary_input() -> None:
    with pytest.raises(TypeError, match="PDAnnotationCircle requires"):
        PDAnnotationCircle(COSString("not-a-dictionary"))  # type: ignore[arg-type]


def test_ink_list_get_path_rejects_non_array_path_entry() -> None:
    ink_list = PDInkList(COSArray([COSString("not-a-path")]))

    with pytest.raises(TypeError, match="expected COSArray"):
        ink_list.get_path(0)
