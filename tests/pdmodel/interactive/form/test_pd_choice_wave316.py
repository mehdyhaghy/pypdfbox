from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox

_I: COSName = COSName.get_pdf_name("I")


def test_wave316_selected_option_indices_accept_cos_number_entries() -> None:
    form = PDAcroForm()
    field = PDListBox(form)
    field.get_cos_object().set_item(
        _I,
        COSArray(
            [
                COSInteger(1),
                COSFloat("2.9"),
                COSString("ignored"),
                COSFloat("-0.7"),
            ]
        ),
    )

    assert field.get_selected_options_indices() == [1, 2, 0]
    assert field.has_selected_options_indices() is True


def test_wave316_selected_option_indices_predicate_requires_numeric_entry() -> None:
    form = PDAcroForm()
    field = PDListBox(form)
    field.get_cos_object().set_item(_I, COSArray([COSString("not numeric")]))

    assert field.get_selected_options_indices() == []
    assert field.has_selected_options_indices() is False
