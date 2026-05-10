"""Wave 272 — round-out cold gaps on ``PDAnnotationScreen``.

Adds has_*/clear_* predicates for the typed sub-entries (/T title, /MK
appearance characteristics, /A action, /AA additional actions). No upstream
Java equivalent — these mirror the same idiom established on
:class:`PDAnnotation` itself (``has_rectangle``/``has_contents``).
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
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

# ---------- /T title predicates ----------


def test_has_title_default_false_wave272() -> None:
    assert PDAnnotationScreen().has_title() is False


def test_has_title_true_after_set_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.set_title("clip1")
    assert ann.has_title() is True


def test_has_title_false_for_empty_string_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.set_title("")
    assert ann.has_title() is False


def test_clear_title_removes_entry_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.set_title("clip1")
    ann.clear_title()
    assert ann.has_title() is False
    assert ann.get_title() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("T"))


def test_clear_title_idempotent_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.clear_title()
    assert ann.has_title() is False


# ---------- /MK appearance-characteristics predicates ----------


def test_has_appearance_characteristics_default_false_wave272() -> None:
    assert PDAnnotationScreen().has_appearance_characteristics() is False


def test_has_appearance_characteristics_true_after_set_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.set_appearance_characteristics(
        PDAppearanceCharacteristicsDictionary(COSDictionary())
    )
    assert ann.has_appearance_characteristics() is True


def test_clear_appearance_characteristics_removes_entry_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.set_appearance_characteristics(
        PDAppearanceCharacteristicsDictionary(COSDictionary())
    )
    ann.clear_appearance_characteristics()
    assert ann.has_appearance_characteristics() is False
    assert ann.get_appearance_characteristics() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("MK"))


# ---------- /A action predicates ----------


def test_has_action_default_false_wave272() -> None:
    assert PDAnnotationScreen().has_action() is False


def test_has_action_true_after_set_wave272() -> None:
    ann = PDAnnotationScreen()
    action = PDActionNamed()
    action.set_n("NextPage")
    ann.set_action(action)
    assert ann.has_action() is True


def test_clear_action_removes_entry_wave272() -> None:
    ann = PDAnnotationScreen()
    action = PDActionNamed()
    action.set_n("NextPage")
    ann.set_action(action)
    ann.clear_action()
    assert ann.has_action() is False
    assert ann.get_action() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("A"))


# ---------- /AA additional-actions predicates ----------


def test_has_additional_actions_default_false_wave272() -> None:
    assert PDAnnotationScreen().has_additional_actions() is False


def test_has_additional_actions_true_after_set_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.set_additional_actions(PDAnnotationAdditionalActions(COSDictionary()))
    assert ann.has_additional_actions() is True


def test_clear_additional_actions_removes_entry_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.set_additional_actions(PDAnnotationAdditionalActions(COSDictionary()))
    ann.clear_additional_actions()
    assert ann.has_additional_actions() is False
    assert ann.get_additional_actions() is None
    # Both alias accessors agree.
    assert ann.get_actions() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("AA"))


# ---------- predicates ignore wrong-type entries ----------


def test_has_action_false_when_entry_is_non_dict_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.get_cos_object().set_name(COSName.get_pdf_name("A"), "junk")
    assert ann.has_action() is False
    assert ann.get_action() is None


def test_has_additional_actions_false_when_entry_is_non_dict_wave272() -> None:
    ann = PDAnnotationScreen()
    ann.get_cos_object().set_name(COSName.get_pdf_name("AA"), "junk")
    assert ann.has_additional_actions() is False
    assert ann.get_additional_actions() is None
