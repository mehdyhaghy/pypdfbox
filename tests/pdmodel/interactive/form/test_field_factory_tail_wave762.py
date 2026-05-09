from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_field_factory import PDFieldFactory
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FF = COSName.get_pdf_name("Ff")
_FT = COSName.get_pdf_name("FT")


def test_wave762_factory_dispatches_from_acroform_field_type_without_parent() -> None:
    form = PDAcroForm()
    form.get_cos_object().set_name(_FT, "Tx")

    result = PDFieldFactory.create_field(form, COSDictionary())

    assert isinstance(result, PDTextField)


def test_wave762_factory_dispatches_from_acroform_button_flags_without_parent() -> None:
    form = PDAcroForm()
    form.get_cos_object().set_name(_FT, "Btn")
    form.get_cos_object().set_int(_FF, PDButton.FLAG_PUSHBUTTON)

    result = PDFieldFactory.create_field(form, COSDictionary())

    assert isinstance(result, PDPushButton)
