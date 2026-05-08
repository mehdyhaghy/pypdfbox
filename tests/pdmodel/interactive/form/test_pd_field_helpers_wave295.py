from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName
from pypdfbox.pdmodel.interactive.action import PDFormFieldAdditionalActions
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_T: COSName = COSName.get_pdf_name("T")
_TU: COSName = COSName.get_pdf_name("TU")
_TM: COSName = COSName.get_pdf_name("TM")
_FF: COSName = COSName.get_pdf_name("Ff")
_AA: COSName = COSName.get_pdf_name("AA")


def _field() -> PDTextField:
    return PDTextField(PDAcroForm())


def test_name_presence_helpers_track_string_like_entries() -> None:
    field = _field()

    field.set_partial_name("personal")
    field.set_alternate_field_name("Personal details")
    field.set_mapping_name("person.details")

    assert field.has_partial_name() is True
    assert field.has_alternate_field_name() is True
    assert field.has_mapping_name() is True

    field.clear_partial_name()
    field.clear_alternate_field_name()
    field.clear_mapping_name()

    assert field.get_partial_name() is None
    assert field.get_alternate_field_name() is None
    assert field.get_mapping_name() is None
    assert field.has_partial_name() is False
    assert field.has_alternate_field_name() is False
    assert field.has_mapping_name() is False


def test_name_presence_helpers_reject_malformed_entries() -> None:
    field = _field()
    field.get_cos_object().set_item(_T, COSArray())
    field.get_cos_object().set_item(_TU, COSDictionary())
    field.get_cos_object().set_item(_TM, COSFloat(1.5))

    assert field.get_partial_name() is None
    assert field.get_alternate_field_name() is None
    assert field.get_mapping_name() is None
    assert field.has_partial_name() is False
    assert field.has_alternate_field_name() is False
    assert field.has_mapping_name() is False


def test_field_flags_presence_helper_is_local_and_typed() -> None:
    field = _field()
    assert field.has_field_flags() is False

    field.set_field_flags(PDTextField.FLAG_MULTILINE)
    assert field.has_field_flags() is True
    assert field.get_field_flags() == PDTextField.FLAG_MULTILINE

    field.clear_field_flags()
    assert field.has_field_flags() is False
    assert field.get_field_flags() == 0

    field.get_cos_object().set_item(_FF, COSName.get_pdf_name("not-an-int"))
    assert field.has_field_flags() is False
    assert field.get_field_flags() == 0


def test_action_presence_helper_tracks_local_dictionary() -> None:
    field = _field()
    actions = PDFormFieldAdditionalActions()

    field.set_actions(actions)
    assert field.has_actions() is True
    assert field.get_actions() is not None

    field.clear_actions()
    assert field.has_actions() is False
    assert field.get_actions() is None

    field.get_cos_object().set_item(_AA, COSArray())
    assert field.has_actions() is False
    assert field.get_actions() is None
