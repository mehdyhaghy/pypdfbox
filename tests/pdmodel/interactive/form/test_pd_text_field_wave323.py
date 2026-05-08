from __future__ import annotations

from pypdfbox.cos import COSDictionary, COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_FT: COSName = COSName.get_pdf_name("FT")
_MAX_LEN: COSName = COSName.get_pdf_name("MaxLen")


def test_wave323_get_max_len_inherits_from_parent_field() -> None:
    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_int(_MAX_LEN, 12)
    parent = PDNonTerminalField(form, parent_dict)

    child_dict = COSDictionary()
    child_dict.set_name(_FT, "Tx")
    field = PDTextField(form, child_dict, parent=parent)

    assert field.get_max_len() == 12
    assert field.has_max_len() is False


def test_wave323_get_max_len_prefers_local_over_inherited_parent() -> None:
    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_int(_MAX_LEN, 12)
    parent = PDNonTerminalField(form, parent_dict)

    child_dict = COSDictionary()
    child_dict.set_name(_FT, "Tx")
    child_dict.set_int(_MAX_LEN, 4)
    field = PDTextField(form, child_dict, parent=parent)

    assert field.get_max_len() == 4
    assert field.has_max_len() is True


def test_wave323_get_max_len_inherits_from_acroform() -> None:
    form = PDAcroForm()
    form.get_cos_object().set_int(_MAX_LEN, 20)

    child_dict = COSDictionary()
    child_dict.set_name(_FT, "Tx")
    field = PDTextField(form, child_dict)

    assert field.get_max_len() == 20
    assert field.has_max_len() is False
