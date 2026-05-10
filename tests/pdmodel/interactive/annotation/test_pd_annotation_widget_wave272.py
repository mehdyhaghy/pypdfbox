"""Wave 272 — round-out cold gaps on ``PDAnnotationWidget``.

Adds has_*/clear_* predicates for the typed sub-dictionaries (/A, /AA, /BS,
/MK, /Parent). No upstream Java equivalent — these mirror the same idiom
already established on :class:`PDAnnotation` itself (``has_rectangle`` etc.)
and exist only to spare callers an extra null-check at the use site.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)

# ---------- /A action predicates ----------


def test_has_action_default_false_wave272() -> None:
    assert PDAnnotationWidget().has_action() is False


def test_has_action_true_after_set_wave272() -> None:
    ann = PDAnnotationWidget()
    ann.set_action(PDActionURI())
    assert ann.has_action() is True


def test_clear_action_removes_entry_wave272() -> None:
    ann = PDAnnotationWidget()
    ann.set_action(PDActionURI())
    ann.clear_action()
    assert ann.has_action() is False
    assert ann.get_action() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("A"))


def test_clear_action_idempotent_wave272() -> None:
    ann = PDAnnotationWidget()
    # No-op when /A is absent.
    ann.clear_action()
    assert ann.has_action() is False


# ---------- /AA additional-actions predicates ----------


def test_has_actions_default_false_wave272() -> None:
    assert PDAnnotationWidget().has_actions() is False


def test_has_actions_true_after_set_wave272() -> None:
    from pypdfbox.pdmodel.interactive.action import PDAnnotationAdditionalActions

    ann = PDAnnotationWidget()
    ann.set_actions(PDAnnotationAdditionalActions())
    assert ann.has_actions() is True


def test_clear_actions_removes_entry_wave272() -> None:
    from pypdfbox.pdmodel.interactive.action import PDAnnotationAdditionalActions

    ann = PDAnnotationWidget()
    ann.set_actions(PDAnnotationAdditionalActions())
    ann.clear_actions()
    assert ann.has_actions() is False
    assert ann.get_actions() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("AA"))


# ---------- /BS border-style predicates ----------


def test_has_border_style_default_false_wave272() -> None:
    assert PDAnnotationWidget().has_border_style() is False


def test_has_border_style_true_after_set_wave272() -> None:
    from pypdfbox.pdmodel.interactive.annotation import PDBorderStyleDictionary

    ann = PDAnnotationWidget()
    ann.set_border_style(PDBorderStyleDictionary(COSDictionary()))
    assert ann.has_border_style() is True


def test_clear_border_style_removes_entry_wave272() -> None:
    from pypdfbox.pdmodel.interactive.annotation import PDBorderStyleDictionary

    ann = PDAnnotationWidget()
    ann.set_border_style(PDBorderStyleDictionary(COSDictionary()))
    ann.clear_border_style()
    assert ann.has_border_style() is False
    assert ann.get_border_style() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("BS"))


# ---------- /MK appearance-characteristics predicates ----------


def test_has_appearance_characteristics_default_false_wave272() -> None:
    assert PDAnnotationWidget().has_appearance_characteristics() is False


def test_has_appearance_characteristics_true_after_set_wave272() -> None:
    from pypdfbox.pdmodel.interactive.annotation import (
        PDAppearanceCharacteristicsDictionary,
    )

    ann = PDAnnotationWidget()
    ann.set_appearance_characteristics(
        PDAppearanceCharacteristicsDictionary(COSDictionary())
    )
    assert ann.has_appearance_characteristics() is True


def test_clear_appearance_characteristics_removes_entry_wave272() -> None:
    from pypdfbox.pdmodel.interactive.annotation import (
        PDAppearanceCharacteristicsDictionary,
    )

    ann = PDAnnotationWidget()
    ann.set_appearance_characteristics(
        PDAppearanceCharacteristicsDictionary(COSDictionary())
    )
    ann.clear_appearance_characteristics()
    assert ann.has_appearance_characteristics() is False
    assert ann.get_appearance_characteristics() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("MK"))


# ---------- /Parent predicates ----------


def test_has_parent_default_false_wave272() -> None:
    assert PDAnnotationWidget().has_parent() is False


def test_has_parent_true_after_set_wave272() -> None:
    ann = PDAnnotationWidget()
    parent = COSDictionary()
    parent.set_string(COSName.get_pdf_name("T"), "field1")
    ann.set_parent(parent)
    assert ann.has_parent() is True


def test_clear_parent_removes_entry_wave272() -> None:
    ann = PDAnnotationWidget()
    parent = COSDictionary()
    parent.set_string(COSName.get_pdf_name("T"), "field1")
    ann.set_parent(parent)
    ann.clear_parent()
    assert ann.has_parent() is False
    assert ann.get_parent() is None
    assert not ann.get_cos_object().contains_key(COSName.get_pdf_name("Parent"))


# ---------- predicates ignore wrong-type entries ----------


def test_has_action_false_when_entry_is_non_dict_wave272() -> None:
    ann = PDAnnotationWidget()
    # Direct-set a non-dictionary value at /A. The typed accessor should
    # ignore it, and so should the predicate.
    ann.get_cos_object().set_name(COSName.get_pdf_name("A"), "junk")
    assert ann.has_action() is False
    assert ann.get_action() is None


def test_has_appearance_characteristics_false_when_entry_is_non_dict_wave272() -> None:
    ann = PDAnnotationWidget()
    ann.get_cos_object().set_name(COSName.get_pdf_name("MK"), "junk")
    assert ann.has_appearance_characteristics() is False
    assert ann.get_appearance_characteristics() is None
