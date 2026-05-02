from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_named import PDActionNamed
from pypdfbox.pdmodel.interactive.action.pd_annotation_additional_actions import (
    PDAnnotationAdditionalActions,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation import PDAnnotation
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_screen import (
    PDAnnotationScreen,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_characteristics_dictionary import (
    PDAppearanceCharacteristicsDictionary,
)


def test_subtype_constant() -> None:
    assert PDAnnotationScreen.SUB_TYPE == "Screen"


def test_default_constructor_sets_subtype() -> None:
    ann = PDAnnotationScreen()
    assert ann.get_subtype() == "Screen"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_extends_annotation_directly_not_markup() -> None:
    # Screen is NOT a markup annotation per PDF 32000-1:2008 Table 170.
    from pypdfbox.pdmodel.interactive.annotation.pd_annotation_markup import (
        PDAnnotationMarkup,
    )

    ann = PDAnnotationScreen()
    assert isinstance(ann, PDAnnotation)
    assert not isinstance(ann, PDAnnotationMarkup)


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Screen")  # type: ignore[attr-defined]
    ann = PDAnnotationScreen(d)
    assert ann.get_subtype() == "Screen"
    assert ann.get_cos_object() is d


def test_title_default_none() -> None:
    assert PDAnnotationScreen().get_title() is None


def test_title_round_trip() -> None:
    ann = PDAnnotationScreen()
    ann.set_title("clip1")
    assert ann.get_title() == "clip1"


def test_appearance_characteristics_default_none() -> None:
    assert PDAnnotationScreen().get_appearance_characteristics() is None


def test_appearance_characteristics_round_trip() -> None:
    ann = PDAnnotationScreen()
    mk = PDAppearanceCharacteristicsDictionary(COSDictionary())
    ann.set_appearance_characteristics(mk)
    got = ann.get_appearance_characteristics()
    assert got is not None
    assert got.get_cos_object() is mk.get_cos_object()


def test_appearance_characteristics_clear() -> None:
    ann = PDAnnotationScreen()
    ann.set_appearance_characteristics(PDAppearanceCharacteristicsDictionary(COSDictionary()))
    ann.set_appearance_characteristics(None)
    assert ann.get_appearance_characteristics() is None


def test_action_default_none() -> None:
    assert PDAnnotationScreen().get_action() is None


def test_action_round_trip() -> None:
    ann = PDAnnotationScreen()
    action = PDActionNamed()
    action.set_n("NextPage")
    ann.set_action(action)
    got = ann.get_action()
    assert isinstance(got, PDActionNamed)
    assert got.get_n() == "NextPage"


def test_action_clear() -> None:
    ann = PDAnnotationScreen()
    ann.set_action(PDActionNamed())
    ann.set_action(None)
    assert ann.get_action() is None


def test_additional_actions_default_none() -> None:
    assert PDAnnotationScreen().get_additional_actions() is None


def test_additional_actions_round_trip() -> None:
    ann = PDAnnotationScreen()
    aa = PDAnnotationAdditionalActions(COSDictionary())
    ann.set_additional_actions(aa)
    got = ann.get_additional_actions()
    assert got is not None
    assert got.get_cos_object() is aa.get_cos_object()


def test_factory_routes_to_screen() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Screen")  # type: ignore[attr-defined]
    ann = PDAnnotation.create(d)
    assert isinstance(ann, PDAnnotationScreen)


# ---------- get_actions / set_actions (Widget-style /AA aliases) ----------


def test_actions_alias_default_none() -> None:
    assert PDAnnotationScreen().get_actions() is None


def test_actions_alias_round_trip() -> None:
    ann = PDAnnotationScreen()
    aa = PDAnnotationAdditionalActions(COSDictionary())
    ann.set_actions(aa)
    got = ann.get_actions()
    assert got is not None
    assert got.get_cos_object() is aa.get_cos_object()
    # Same backing /AA dict — both accessor pairs see it.
    assert ann.get_additional_actions() is not None
    assert ann.get_additional_actions().get_cos_object() is aa.get_cos_object()


def test_actions_alias_clear() -> None:
    ann = PDAnnotationScreen()
    ann.set_actions(PDAnnotationAdditionalActions(COSDictionary()))
    ann.set_actions(None)
    assert ann.get_actions() is None
    assert ann.get_additional_actions() is None


def test_actions_alias_writes_through_to_long_name() -> None:
    # Setting via the long-form name is observable via the short alias.
    ann = PDAnnotationScreen()
    aa = PDAnnotationAdditionalActions(COSDictionary())
    ann.set_additional_actions(aa)
    got = ann.get_actions()
    assert got is not None
    assert got.get_cos_object() is aa.get_cos_object()
