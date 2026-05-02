from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action import PDAction
from pypdfbox.pdmodel.interactive.action.pd_action_go_to_3d_view import (
    PDActionGoTo3DView,
)

_S: COSName = COSName.get_pdf_name("S")
_TYPE: COSName = COSName.get_pdf_name("Type")
_TA: COSName = COSName.get_pdf_name("TA")
_V: COSName = COSName.get_pdf_name("V")


def test_default_construction_sets_type_and_subtype() -> None:
    action = PDActionGoTo3DView()
    cos = action.get_cos_object()
    assert cos.get_name(_TYPE) == "Action"
    assert cos.get_name(_S) == "GoTo3DView"
    assert action.get_sub_type() == "GoTo3DView"


def test_sub_type_constant() -> None:
    assert PDActionGoTo3DView.SUB_TYPE == "GoTo3DView"


def test_named_view_constants() -> None:
    assert PDActionGoTo3DView.VIEW_FIRST == "F"
    assert PDActionGoTo3DView.VIEW_LAST == "L"
    assert PDActionGoTo3DView.VIEW_NEXT == "N"
    assert PDActionGoTo3DView.VIEW_PREVIOUS == "P"


def test_target_annotation_round_trip_via_cos_dictionary() -> None:
    action = PDActionGoTo3DView()
    annotation = COSDictionary()
    action.set_target_annotation(annotation)

    assert action.get_target_annotation() is annotation
    assert action.get_ta() is annotation


def test_target_annotation_alias_setter() -> None:
    action = PDActionGoTo3DView()
    annotation = COSDictionary()
    action.set_ta(annotation)
    assert action.get_target_annotation() is annotation


def test_target_annotation_remove_via_none() -> None:
    action = PDActionGoTo3DView()
    annotation = COSDictionary()
    action.set_target_annotation(annotation)
    action.set_target_annotation(None)
    assert action.get_target_annotation() is None


def test_v_named_view_first() -> None:
    action = PDActionGoTo3DView()
    action.set_v(PDActionGoTo3DView.VIEW_FIRST)
    cos = action.get_cos_object()
    assert cos.get_name(_V) == "F"


def test_v_named_view_last() -> None:
    action = PDActionGoTo3DView()
    action.set_v(PDActionGoTo3DView.VIEW_LAST)
    cos = action.get_cos_object()
    assert cos.get_name(_V) == "L"


def test_v_named_view_next() -> None:
    action = PDActionGoTo3DView()
    action.set_v(PDActionGoTo3DView.VIEW_NEXT)
    assert action.get_cos_object().get_name(_V) == "N"


def test_v_named_view_previous() -> None:
    action = PDActionGoTo3DView()
    action.set_v(PDActionGoTo3DView.VIEW_PREVIOUS)
    assert action.get_cos_object().get_name(_V) == "P"


def test_v_integer_index() -> None:
    action = PDActionGoTo3DView()
    action.set_v(3)
    raw = action.get_v()
    assert isinstance(raw, COSInteger)
    assert raw.int_value() == 3


def test_v_internal_name_string() -> None:
    """Non-named-view strings are stored as ``COSString`` and match the
    ``/IN`` internal-name lookup path per PDF 32000-1 §12.6.4.16."""
    action = PDActionGoTo3DView()
    action.set_v("OrthographicLeft")
    raw = action.get_v()
    assert isinstance(raw, COSString)
    assert raw.get_string() == "OrthographicLeft"


def test_v_view_dictionary() -> None:
    action = PDActionGoTo3DView()
    view_dict = COSDictionary()
    action.set_v(view_dict)
    assert action.get_v() is view_dict


def test_v_remove_via_none() -> None:
    action = PDActionGoTo3DView()
    action.set_v(7)
    action.set_v(None)
    assert action.get_v() is None


def test_v_rejects_bool() -> None:
    """Reject bool to avoid silent 0/1 conversion when the caller meant
    a different value type."""
    action = PDActionGoTo3DView()
    with pytest.raises(TypeError):
        action.set_v(True)


def test_factory_dispatch_returns_pd_action_go_to_3d_view() -> None:
    """``PDAction.create`` dispatches a ``/S /GoTo3DView`` dictionary to
    :class:`PDActionGoTo3DView`."""
    cos = COSDictionary()
    cos.set_name(_S, "GoTo3DView")
    resolved = PDAction.create(cos)
    assert isinstance(resolved, PDActionGoTo3DView)


def test_round_trip_through_cos_dictionary() -> None:
    """A populated action survives serialization to ``COSDictionary`` and
    rehydration through the explicit-COSDictionary constructor."""
    annotation = COSDictionary()
    action = PDActionGoTo3DView()
    action.set_target_annotation(annotation)
    action.set_v(PDActionGoTo3DView.VIEW_NEXT)

    rehydrated = PDActionGoTo3DView(action.get_cos_object())
    assert rehydrated.get_target_annotation() is annotation
    assert rehydrated.get_cos_object().get_name(_V) == "N"
    assert rehydrated.get_sub_type() == "GoTo3DView"


def test_explicit_cos_construction_does_not_override_sub_type() -> None:
    """When constructed with an existing dictionary, the wrapper does not
    overwrite an existing ``/S`` entry."""
    cos = COSDictionary()
    cos.set_name(_S, "GoTo3DView")
    action = PDActionGoTo3DView(cos)
    assert action.get_sub_type() == "GoTo3DView"


# ---------- typed-accessor coverage ----------


def test_get_target_annotation_dictionary_returns_typed_dict() -> None:
    action = PDActionGoTo3DView()
    annotation = COSDictionary()
    action.set_target_annotation(annotation)
    assert action.get_target_annotation_dictionary() is annotation


def test_get_target_annotation_dictionary_returns_none_when_absent() -> None:
    action = PDActionGoTo3DView()
    assert action.get_target_annotation_dictionary() is None


def test_get_target_annotation_dictionary_returns_none_for_non_dict() -> None:
    """When ``/TA`` is set to a non-dictionary COS object the typed
    accessor returns ``None`` rather than coercing or raising."""
    action = PDActionGoTo3DView()
    action.get_cos_object().set_name(_TA, "NotADict")
    assert action.get_target_annotation_dictionary() is None
    # Raw accessor still surfaces the underlying entry.
    assert action.get_target_annotation() is not None


def test_get_v_named_returns_letter_for_named_view() -> None:
    action = PDActionGoTo3DView()
    action.set_v(PDActionGoTo3DView.VIEW_NEXT)
    assert action.get_v_named() == "N"
    assert action.get_v_index() is None
    assert action.get_v_internal_name() is None


def test_get_v_named_returns_none_for_unknown_name() -> None:
    """A ``COSName`` that is not one of the four spec named-view selectors
    must NOT be returned by :meth:`get_v_named`."""
    action = PDActionGoTo3DView()
    action.get_cos_object().set_name(_V, "Z")
    assert action.get_v_named() is None


def test_get_v_index_returns_integer_when_v_is_int() -> None:
    action = PDActionGoTo3DView()
    action.set_v(5)
    assert action.get_v_index() == 5
    assert action.get_v_named() is None
    assert action.get_v_internal_name() is None


def test_get_v_internal_name_returns_string_when_v_is_string() -> None:
    action = PDActionGoTo3DView()
    action.set_v("Top")
    assert action.get_v_internal_name() == "Top"
    assert action.get_v_named() is None
    assert action.get_v_index() is None


def test_get_v_typed_accessors_return_none_when_v_absent() -> None:
    action = PDActionGoTo3DView()
    assert action.get_v_named() is None
    assert action.get_v_index() is None
    assert action.get_v_internal_name() is None


def test_is_named_view_classmethod_true_for_each_named_value() -> None:
    for value in ("F", "L", "N", "P"):
        assert PDActionGoTo3DView.is_named_view(value) is True


def test_is_named_view_classmethod_false_for_other_strings() -> None:
    for value in ("", "f", "n", "First", "FF", "Q"):
        assert PDActionGoTo3DView.is_named_view(value) is False
