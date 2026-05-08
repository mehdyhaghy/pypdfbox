from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName
from pypdfbox.pdmodel.interactive.action.pd_action_go_to_3d_view import (
    PDActionGoTo3DView,
)

_S: COSName = COSName.get_pdf_name("S")
_TA: COSName = COSName.get_pdf_name("TA")
_V: COSName = COSName.get_pdf_name("V")


def test_has_target_annotation_requires_dictionary_wave295() -> None:
    action = PDActionGoTo3DView()
    assert action.has_target_annotation() is False
    assert action.is_empty() is True

    action.get_cos_object().set_item(_TA, COSName.get_pdf_name("NotAnAnnotation"))
    assert action.get_target_annotation() is not None
    assert action.has_target_annotation() is False
    assert action.is_empty() is True

    target = COSDictionary()
    action.set_target_annotation(target)
    assert action.has_target_annotation() is True
    assert action.is_empty() is False


def test_clear_target_annotation_removes_ta_wave295() -> None:
    action = PDActionGoTo3DView()
    action.set_target_annotation(COSDictionary())
    assert action.has_target_annotation() is True

    action.clear_target_annotation()
    assert action.get_target_annotation() is None
    assert action.has_target_annotation() is False


def test_has_v_accepts_supported_view_shapes_wave295() -> None:
    action = PDActionGoTo3DView()
    assert action.has_v() is False

    action.set_v(PDActionGoTo3DView.VIEW_NEXT)
    assert action.has_v() is True

    action.set_v(2)
    assert action.has_v() is True

    action.set_v("NamedView")
    assert action.has_v() is True

    action.set_v(COSDictionary())
    assert action.has_v() is True


def test_has_v_rejects_malformed_view_shapes_wave295() -> None:
    action = PDActionGoTo3DView()

    action.get_cos_object().set_name(_V, "UnknownViewSelector")
    assert action.get_v() is not None
    assert action.get_v_named() is None
    assert action.has_v() is False

    action.get_cos_object().set_item(_V, COSArray([COSInteger.get(1)]))
    assert action.get_v() is not None
    assert action.has_v() is False


def test_clear_v_removes_view_selector_wave295() -> None:
    action = PDActionGoTo3DView()
    action.set_v(PDActionGoTo3DView.VIEW_FIRST)
    assert action.has_v() is True

    action.clear_v()
    assert action.get_v() is None
    assert action.has_v() is False


def test_is_valid_checks_goto_3d_view_subtype_wave295() -> None:
    assert PDActionGoTo3DView().is_valid() is True

    raw = COSDictionary()
    raw.set_name(_S, "GoTo")
    assert PDActionGoTo3DView(raw).is_valid() is False
