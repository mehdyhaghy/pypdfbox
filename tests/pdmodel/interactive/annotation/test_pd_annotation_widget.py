from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField


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
    from pypdfbox.pdmodel.interactive.action import PDAnnotationAdditionalActions

    ann = PDAnnotationWidget()
    aa = COSDictionary()
    aa.set_name(COSName.TYPE, "AA")  # type: ignore[attr-defined]
    ann.set_actions(aa)
    resolved = ann.get_actions()
    assert isinstance(resolved, PDAnnotationAdditionalActions)
    assert resolved.get_cos_object() is aa
    ann.set_actions(None)
    assert ann.get_actions() is None


def test_actions_round_trip_annotation_additional_actions_wrapper() -> None:
    from pypdfbox.pdmodel.interactive.action import PDAnnotationAdditionalActions

    ann = PDAnnotationWidget()
    actions = PDAnnotationAdditionalActions()
    actions.set_e(PDActionURI())

    ann.set_actions(actions)

    resolved = ann.get_actions()
    assert isinstance(resolved, PDAnnotationAdditionalActions)
    assert resolved.get_cos_object() is actions.get_cos_object()
    assert isinstance(resolved.get_e(), PDActionURI)


def test_border_style_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.annotation import PDBorderStyleDictionary

    ann = PDAnnotationWidget()
    bs = COSDictionary()
    bs.set_name(COSName.TYPE, "Border")  # type: ignore[attr-defined]
    bs.set_int(COSName.get_pdf_name("W"), 3)
    ann.set_border_style(bs)
    resolved = ann.get_border_style()
    assert isinstance(resolved, PDBorderStyleDictionary)
    assert resolved.get_cos_object() is bs
    ann.set_border_style(None)
    assert ann.get_border_style() is None


def test_appearance_characteristics_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.annotation import (
        PDAppearanceCharacteristicsDictionary,
    )

    ann = PDAnnotationWidget()
    mk = COSDictionary()
    mk.set_int(COSName.get_pdf_name("R"), 90)
    ann.set_appearance_characteristics(mk)
    resolved = ann.get_appearance_characteristics()
    assert isinstance(resolved, PDAppearanceCharacteristicsDictionary)
    assert resolved.get_cos_object() is mk
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


def test_set_parent_accepts_pd_terminal_field() -> None:
    ann = PDAnnotationWidget()
    field = PDTextField(PDAcroForm())
    field.set_partial_name("field1")

    ann.set_parent(field)

    assert ann.get_parent() is field.get_cos_object()
    assert (
        ann.get_cos_object().get_dictionary_object(COSName.get_pdf_name("Parent"))
        is field.get_cos_object()
    )


def test_set_parent_rejects_shared_widget_field_dictionary() -> None:
    field = PDTextField(PDAcroForm())
    ann = field.get_widgets()[0]

    with pytest.raises(ValueError, match="shares a dictionary"):
        ann.set_parent(field)


# ---------- /H highlighting-mode constants (PDF 32000-1 Table 188) ----------


def test_highlight_mode_constants_match_spec() -> None:
    cls = PDAnnotationWidget
    assert cls.HIGHLIGHT_MODE_NONE == "N"
    assert cls.HIGHLIGHT_MODE_INVERT == "I"
    assert cls.HIGHLIGHT_MODE_OUTLINE == "O"
    assert cls.HIGHLIGHT_MODE_PUSH == "P"
    assert cls.HIGHLIGHT_MODE_TOGGLE == "T"


def test_highlight_mode_constants_round_trip_via_setter() -> None:
    cls = PDAnnotationWidget
    for mode in (
        cls.HIGHLIGHT_MODE_NONE,
        cls.HIGHLIGHT_MODE_INVERT,
        cls.HIGHLIGHT_MODE_OUTLINE,
        cls.HIGHLIGHT_MODE_PUSH,
        cls.HIGHLIGHT_MODE_TOGGLE,
    ):
        ann = cls()
        ann.set_highlighting_mode(mode)
        assert ann.get_highlighting_mode() == mode


def test_highlight_mode_invalid_value_raises() -> None:
    ann = PDAnnotationWidget()
    with pytest.raises(ValueError, match="Invalid highlighting mode"):
        ann.set_highlighting_mode("Z")
