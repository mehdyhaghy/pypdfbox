"""Wave 277 focused coverage for :class:`PDActionHide`.

The implementation already exposes the useful narrow conveniences for
``/T`` and ``/H``. These tests lock down the remaining shapes: all legal
target forms, default/set/clear hide semantics, factory round-tripping,
and malformed target values that should be ignored rather than raising.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSBoolean, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_hide import PDActionHide
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_link import (
    PDAnnotationLink,
)
from pypdfbox.pdmodel.interactive.annotation.pd_annotation_widget import (
    PDAnnotationWidget,
)

_H: COSName = COSName.get_pdf_name("H")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")
_T: COSName = COSName.T  # type: ignore[attr-defined]


def _annotation_dict(subtype: str = "Widget") -> COSDictionary:
    annot = COSDictionary()
    annot.set_name(_SUBTYPE, subtype)
    return annot


def test_t_string_form_is_exposed_as_target_name_only() -> None:
    action = PDActionHide()
    action.set_target(COSString("Page1.FieldA"))

    assert action.has_target() is True
    assert action.get_target_names() == ["Page1.FieldA"]
    assert action.get_annotation() is None
    assert action.get_annotations() == []


def test_t_array_form_preserves_mixed_string_and_annotation_views() -> None:
    action = PDActionHide()
    widget = _annotation_dict("Widget")
    link = _annotation_dict("Link")
    target = COSArray([COSString("FieldA"), widget, COSString("FieldB"), link])
    action.set_target(target)

    assert action.get_target() is target
    assert action.get_target_names() == ["FieldA", "FieldB"]

    annotations = action.get_annotations()
    assert annotations is not None
    assert [type(annotation) for annotation in annotations] == [
        PDAnnotationWidget,
        PDAnnotationLink,
    ]
    assert [annotation.get_cos_object() for annotation in annotations] == [
        widget,
        link,
    ]


def test_t_raw_dict_and_wrapper_forms_store_annotation_dictionary() -> None:
    action = PDActionHide()
    raw = _annotation_dict("Widget")
    action.set_annotation(raw)

    from_raw = action.get_annotation()
    assert isinstance(from_raw, PDAnnotationWidget)
    assert from_raw.get_cos_object() is raw

    widget = PDAnnotationWidget()
    action.set_annotation(widget)

    assert action.get_target() is widget.get_cos_object()
    from_wrapper = action.get_annotation()
    assert isinstance(from_wrapper, PDAnnotationWidget)
    assert from_wrapper.get_cos_object() is widget.get_cos_object()


def test_hide_flag_defaults_sets_and_clears_without_losing_wire_shape() -> None:
    action = PDActionHide()

    assert action.get_h() is True
    assert action.should_hide() is True
    assert action.has_hide_flag() is False
    assert action.get_cos_object().get_dictionary_object(_H) is None

    action.set_h(False)
    assert action.get_h() is False
    assert action.has_hide_flag() is True
    assert action.get_cos_object().get_dictionary_object(_H) is COSBoolean.FALSE

    action.set_hide(True)
    assert action.is_hide() is True
    assert action.has_hide_flag() is True
    assert action.get_cos_object().get_dictionary_object(_H) is COSBoolean.TRUE

    action.clear_hide_flag()
    assert action.get_h() is True
    assert action.has_hide_flag() is False
    assert action.get_cos_object().get_dictionary_object(_H) is None


def test_cos_round_trip_through_action_factory_preserves_target_and_hide_flag() -> None:
    action = PDActionHide()
    action.set_target(
        COSArray(
            [
                COSString("FieldA"),
                PDAnnotationWidget().get_cos_object(),
                COSString("FieldB"),
            ]
        )
    )
    action.set_h(False)

    parsed = PDAction.create(action.get_cos_object())

    assert isinstance(parsed, PDActionHide)
    assert parsed.get_cos_object() is action.get_cos_object()
    assert parsed.get_target_names() == ["FieldA", "FieldB"]
    annotations = parsed.get_annotations()
    assert annotations is not None
    assert len(annotations) == 1
    assert isinstance(annotations[0], PDAnnotationWidget)
    assert parsed.get_h() is False


def test_malformed_scalar_target_shape_is_safe_for_typed_views() -> None:
    action = PDActionHide()
    action.get_cos_object().set_item(_T, COSName.get_pdf_name("NotATargetShape"))

    assert action.has_target() is True
    assert action.get_target_names() == []
    assert action.get_annotation() is None
    assert action.get_annotations() == []


def test_malformed_array_target_shape_skips_unsupported_entries() -> None:
    action = PDActionHide()
    widget = _annotation_dict("Widget")
    action.set_target(
        COSArray(
            [
                COSName.get_pdf_name("Bogus"),
                COSBoolean.TRUE,
                COSString("FieldA"),
                widget,
            ]
        )
    )

    assert action.get_target_names() == ["FieldA"]
    annotations = action.get_annotations()
    assert annotations is not None
    assert len(annotations) == 1
    assert isinstance(annotations[0], PDAnnotationWidget)
    assert annotations[0].get_cos_object() is widget


def test_malformed_hide_flag_shape_falls_back_to_table_200_default() -> None:
    action = PDActionHide()
    action.get_cos_object().set_item(_H, COSString("false"))

    assert action.has_hide_flag() is True
    assert action.get_h() is True
    assert action.should_hide() is True
