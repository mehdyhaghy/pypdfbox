from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_AP = COSName.get_pdf_name("AP")
_DA = COSName.get_pdf_name("DA")
_DS = COSName.get_pdf_name("DS")
_FT = COSName.get_pdf_name("FT")
_KIDS = COSName.get_pdf_name("Kids")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_RV = COSName.get_pdf_name("RV")
_T = COSName.get_pdf_name("T")


def _widget_with_normal_appearance(normal: object) -> PDAnnotationWidget:
    widget = PDAnnotationWidget()
    ap = COSDictionary()
    ap.set_item(_N, normal)
    widget.get_cos_object().set_item(_AP, ap)
    return widget


def test_wave761_non_terminal_children_skip_non_dict_and_self_reference() -> None:
    form = PDAcroForm()
    parent_dict = COSDictionary()
    child_dict = COSDictionary()
    child_dict.set_name(_FT, "Tx")
    child_dict.set_string(_T, "child")

    kids = COSArray()
    kids.add(COSString("not-a-field-dictionary"))
    kids.add(parent_dict)
    kids.add(child_dict)
    parent_dict.set_item(_KIDS, kids)

    children = PDNonTerminalField(form, parent_dict).get_children()

    assert len(children) == 1
    assert isinstance(children[0], PDTextField)
    assert children[0].get_cos_object() is child_dict


def test_wave761_non_terminal_array_value_stringifies_unknown_entries() -> None:
    form = PDAcroForm()
    field = PDNonTerminalField(form)
    fallback = COSDictionary()
    values = COSArray()
    values.add(COSString("alpha"))
    values.add(COSName.get_pdf_name("Beta"))
    values.add(fallback)

    field.set_value(values)

    assert field.get_value_as_string() == f"alpha,Beta,{fallback}"


def test_wave761_non_terminal_value_as_string_falls_back_to_cos_str() -> None:
    form = PDAcroForm()
    field = PDNonTerminalField(form)
    value = COSDictionary()

    field.set_value(value)

    assert field.get_value_as_string() == str(value)


def test_wave761_check_box_non_dictionary_normal_appearance_has_no_on_value() -> None:
    checkbox = PDCheckBox(PDAcroForm())
    checkbox.set_widgets([_widget_with_normal_appearance(COSString("bad-normal"))])

    assert checkbox.get_on_value() == ""
    checkbox.check()
    assert checkbox.get_value() == "Yes"


def test_wave761_check_box_off_only_normal_appearance_has_no_on_value() -> None:
    checkbox = PDCheckBox(PDAcroForm())
    normal = COSDictionary()
    normal.set_item(_OFF, COSDictionary())
    checkbox.set_widgets([_widget_with_normal_appearance(normal)])

    assert checkbox.get_on_value() == ""
    checkbox.check()
    assert checkbox.get_value() == "Yes"


def test_wave761_check_box_is_checked_uses_discovered_on_value() -> None:
    checkbox = PDCheckBox(PDAcroForm())
    normal = COSDictionary()
    normal.set_item(COSName.get_pdf_name("Accepted"), COSDictionary())
    normal.set_item(_OFF, COSDictionary())
    checkbox.set_widgets([_widget_with_normal_appearance(normal)])

    checkbox.set_value("Accepted")
    assert checkbox.is_checked() is True

    checkbox.set_value("Off")
    assert checkbox.is_checked() is False


def test_wave761_variable_text_clear_default_style_string_removes_local_ds() -> None:
    field = PDTextField(PDAcroForm())
    field.set_default_style_string("font: Helvetica")

    field.clear_default_style_string()

    assert field.has_default_style_string() is False
    assert field.get_cos_object().get_dictionary_object(_DS) is None


def test_wave761_variable_text_clear_rich_text_value_removes_local_rv() -> None:
    field = PDTextField(PDAcroForm())
    field.set_rich_text_value("<body>Hi</body>")

    field.clear_rich_text_value()

    assert field.has_rich_text_value() is False
    assert field.get_cos_object().get_dictionary_object(_RV) is None


def test_wave761_variable_text_clear_default_appearance_removes_local_da() -> None:
    field = PDTextField(PDAcroForm())
    field.set_default_appearance("/Helv 12 Tf 0 g")

    field.clear_default_appearance()

    assert field.has_default_appearance() is False
    assert field.get_cos_object().get_dictionary_object(_DA) is None
