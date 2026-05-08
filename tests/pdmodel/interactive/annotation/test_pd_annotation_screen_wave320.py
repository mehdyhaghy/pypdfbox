from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
    PDAnnotationAdditionalActions,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
    PDAnnotationScreen,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)


class _NonDictionaryBacked:
    def get_cos_object(self) -> COSArray:
        return COSArray()


def test_set_appearance_characteristics_rejects_raw_non_dictionary_wave320() -> None:
    ann = PDAnnotationScreen()

    with pytest.raises(TypeError, match="set_appearance_characteristics expects"):
        ann.set_appearance_characteristics(COSArray())  # type: ignore[arg-type]

    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("MK"))


def test_set_appearance_characteristics_rejects_non_dictionary_wrapper_wave320() -> None:
    ann = PDAnnotationScreen()

    with pytest.raises(TypeError, match="COSDictionary-backed wrapper"):
        ann.set_appearance_characteristics(_NonDictionaryBacked())  # type: ignore[arg-type]

    assert ann.get_appearance_characteristics() is None


def test_set_action_rejects_raw_non_dictionary_without_replacing_existing_wave320() -> None:
    ann = PDAnnotationScreen()
    action = PDActionNamed()
    action.set_n("NextPage")
    ann.set_action(action)
    original = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("A"))

    with pytest.raises(TypeError, match="set_action expects"):
        ann.set_action(COSArray())  # type: ignore[arg-type]

    assert ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("A")) is original
    got = ann.get_action()
    assert isinstance(got, PDActionNamed)
    assert got.get_n() == "NextPage"


def test_set_action_rejects_non_dictionary_wrapper_wave320() -> None:
    ann = PDAnnotationScreen()

    with pytest.raises(TypeError, match="COSDictionary-backed wrapper"):
        ann.set_action(_NonDictionaryBacked())  # type: ignore[arg-type]

    assert ann.get_action() is None


def test_set_additional_actions_rejects_raw_non_dictionary_wave320() -> None:
    ann = PDAnnotationScreen()

    with pytest.raises(TypeError, match="set_additional_actions expects"):
        ann.set_additional_actions(COSArray())  # type: ignore[arg-type]

    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("AA"))


def test_set_actions_alias_rejects_non_dictionary_wrapper_wave320() -> None:
    ann = PDAnnotationScreen()
    actions = PDAnnotationAdditionalActions(COSDictionary())
    ann.set_actions(actions)
    original = ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AA"))

    with pytest.raises(TypeError, match="COSDictionary-backed wrapper"):
        ann.set_actions(_NonDictionaryBacked())  # type: ignore[arg-type]

    assert ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AA")) is original
    assert ann.get_actions() is not None


def test_valid_dictionary_backed_screen_setters_still_round_trip_wave320() -> None:
    ann = PDAnnotationScreen()
    mk = PDAppearanceCharacteristicsDictionary(COSDictionary())
    aa = PDAnnotationAdditionalActions(COSDictionary())

    ann.set_appearance_characteristics(mk)
    ann.set_additional_actions(aa)

    got_mk = ann.get_appearance_characteristics()
    got_aa = ann.get_additional_actions()
    assert got_mk is not None
    assert got_mk.get_cos_object() is mk.get_cos_object()
    assert got_aa is not None
    assert got_aa.get_cos_object() is aa.get_cos_object()
