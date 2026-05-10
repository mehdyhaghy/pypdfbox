"""Wave 1275 — PDVariableText.get_default_appearance_string."""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.interactive.form.pd_variable_text import (
    PDDefaultAppearanceString,
)
from pypdfbox.pdmodel.pd_resources import PDResources

_DA = COSName.get_pdf_name("DA")
_DR = COSName.get_pdf_name("DR")


def _form_with_default_resources(da: str | None = "/Helv 12 Tf 0 g") -> PDAcroForm:
    form = PDAcroForm()
    if da is not None:
        form.get_cos_object().set_string(_DA, da)
    form.get_cos_object().set_item(_DR, COSDictionary())
    return form


def test_returns_pd_default_appearance_string_instance() -> None:
    form = _form_with_default_resources()
    field = PDTextField(form)
    result = field.get_default_appearance_string()
    assert isinstance(result, PDDefaultAppearanceString)


def test_returns_da_via_inheritable_attribute() -> None:
    form = _form_with_default_resources("/Cour 10 Tf 1 g")
    field = PDTextField(form)
    # Field inherits /DA from the AcroForm.
    da_string = field.get_default_appearance_string()
    assert da_string is not None
    assert da_string.get_default_appearance().get_string() == "/Cour 10 Tf 1 g"


def test_returns_typed_pd_resources() -> None:
    form = _form_with_default_resources()
    field = PDTextField(form)
    result = field.get_default_appearance_string()
    assert result is not None
    assert isinstance(result.get_default_resources(), PDResources)


def test_returns_none_when_da_absent() -> None:
    form = PDAcroForm()
    form.get_cos_object().set_item(_DR, COSDictionary())
    field = PDTextField(form)
    assert field.get_default_appearance_string() is None


def test_constructor_rejects_none_da() -> None:
    with pytest.raises(ValueError, match="/DA"):
        PDDefaultAppearanceString(None, PDResources())


def test_constructor_rejects_none_resources() -> None:
    with pytest.raises(ValueError, match="/DR"):
        PDDefaultAppearanceString(COSString("/Helv 12 Tf 0 g"), None)
