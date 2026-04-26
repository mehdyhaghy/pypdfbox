from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)


def test_default_constructor_sets_widget_subtype() -> None:
    ann = PDAnnotationWidget()
    assert ann.get_subtype() == "Widget"
    assert ann.get_cos_object().get_name(COSName.TYPE) == "Annot"  # type: ignore[attr-defined]


def test_constructor_with_dict_preserves_subtype() -> None:
    d = COSDictionary()
    d.set_name(COSName.SUBTYPE, "Widget")  # type: ignore[attr-defined]
    ann = PDAnnotationWidget(d)
    assert ann.get_subtype() == "Widget"


def test_subtype_constant() -> None:
    assert PDAnnotationWidget.SUB_TYPE == "Widget"


def test_highlighting_mode_default_invert() -> None:
    ann = PDAnnotationWidget()
    assert ann.get_highlighting_mode() == "I"


def test_highlighting_mode_round_trip() -> None:
    ann = PDAnnotationWidget()
    ann.set_highlighting_mode("I")
    assert ann.get_highlighting_mode() == "I"
    ann.set_highlighting_mode("P")
    assert ann.get_highlighting_mode() == "P"
    ann.set_highlighting_mode(None)
    assert ann.get_highlighting_mode() == "I"


def test_action_round_trip() -> None:
    ann = PDAnnotationWidget()
    action = PDActionURI()
    action.set_uri("https://example.test/widget")
    ann.set_action(action)
    rt = ann.get_action()
    assert isinstance(rt, PDActionURI)
    assert rt.get_uri() == "https://example.test/widget"


def test_action_default_none() -> None:
    ann = PDAnnotationWidget()
    assert ann.get_action() is None


def test_action_clear() -> None:
    ann = PDAnnotationWidget()
    ann.set_action(PDActionURI())
    ann.set_action(None)
    assert ann.get_action() is None


def test_actions_aa_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions

    ann = PDAnnotationWidget()
    aa = COSDictionary()
    aa.set_name(COSName.TYPE, "AA")  # type: ignore[attr-defined]
    ann.set_actions(aa)
    resolved = ann.get_actions()
    assert isinstance(resolved, PDFormFieldAdditionalActions)
    assert resolved.get_cos_object() is aa
    ann.set_actions(None)
    assert ann.get_actions() is None


def test_border_style_round_trip() -> None:
    ann = PDAnnotationWidget()
    bs = COSDictionary()
    bs.set_name(COSName.TYPE, "Border")  # type: ignore[attr-defined]
    bs.set_int(COSName.get_pdf_name("W"), 3)
    ann.set_border_style(bs)
    assert ann.get_border_style() is bs
    ann.set_border_style(None)
    assert ann.get_border_style() is None


def test_appearance_characteristics_round_trip() -> None:
    ann = PDAnnotationWidget()
    mk = COSDictionary()
    mk.set_int(COSName.get_pdf_name("R"), 90)
    ann.set_appearance_characteristics(mk)
    assert ann.get_appearance_characteristics() is mk
    ann.set_appearance_characteristics(None)
    assert ann.get_appearance_characteristics() is None


def test_parent_round_trip() -> None:
    ann = PDAnnotationWidget()
    parent = COSDictionary()
    parent.set_string(COSName.get_pdf_name("T"), "field1")
    ann.set_parent(parent)
    assert ann.get_parent() is parent
    ann.set_parent(None)
    assert ann.get_parent() is None
