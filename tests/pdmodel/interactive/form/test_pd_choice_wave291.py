from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox

_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_I: COSName = COSName.get_pdf_name("I")


def test_choice_value_presence_rejects_malformed_arrays() -> None:
    field = PDListBox(PDAcroForm())
    cos = field.get_cos_object()

    malformed = COSArray([COSInteger(7)])
    cos.set_item(_V, malformed)
    assert field.get_value() == []
    assert field.has_value() is False

    malformed.add(COSString("valid"))
    assert field.get_value() == ["valid"]
    assert field.has_value() is True


def test_choice_default_value_presence_rejects_malformed_arrays() -> None:
    field = PDListBox(PDAcroForm())
    cos = field.get_cos_object()

    malformed = COSArray([COSInteger(7)])
    cos.set_item(_DV, malformed)
    assert field.get_default_value() == []
    assert field.has_default_value() is False

    malformed.add(COSName.get_pdf_name("ExportName"))
    assert field.get_default_value() == ["ExportName"]
    assert field.has_default_value() is True


def test_choice_selected_index_presence_rejects_malformed_arrays() -> None:
    field = PDListBox(PDAcroForm())
    cos = field.get_cos_object()

    malformed = COSArray([COSString("not-an-index")])
    cos.set_item(_I, malformed)
    assert field.get_selected_options_indices() == []
    assert field.has_selected_options_indices() is False

    malformed.add(COSInteger(2))
    assert field.get_selected_options_indices() == [2]
    assert field.has_selected_options_indices() is True
