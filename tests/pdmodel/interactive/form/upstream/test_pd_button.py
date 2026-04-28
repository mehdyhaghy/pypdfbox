"""Ported from upstream PDFBox 3.0 ``PDButtonTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDButtonTest.java``

Skipped upstream cases — all require external Acrobat-generated PDFs
fetched from ``target/pdfs/`` by the Maven harness:
``testRadioButtonWithOptions``, ``testOptionsAndNamesNotNumbers``,
``retrieveAcrobatCheckBoxProperties``, ``testAcrobatCheckBoxProperties``,
``setValueForAbstractedAcrobatCheckBox``, ``testAcrobatCheckBoxGroupProperties``,
``setValueForAbstractedCheckBoxGroup``, ``setCheckboxInvalidValue``,
``setCheckboxGroupInvalidValue``, ``setAbstractedCheckboxInvalidValue``,
``setAbstractedCheckboxGroupInvalidValue``,
``retrieveAcrobatRadioButtonProperties``, ``testAcrobatRadioButtonProperties``,
``setValueForAbstractedAcrobatRadioButton``, ``setRadioButtonInvalidValue``,
``setAbstractedRadioButtonInvalidValue``.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSName
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton

_FT: COSName = COSName.get_pdf_name("FT")


@pytest.fixture
def acro_form() -> PDAcroForm:
    return PDAcroForm()


def test_create_check_box(acro_form: PDAcroForm) -> None:
    """Upstream: ``createCheckBox``."""
    button_field = PDCheckBox(acro_form)
    assert button_field.get_field_type() == button_field.get_cos_object().get_name(_FT)
    assert button_field.get_field_type() == "Btn"
    assert button_field.is_push_button() is False
    assert button_field.is_radio_button() is False


def test_create_push_button(acro_form: PDAcroForm) -> None:
    """Upstream: ``createPushButton``."""
    button_field = PDPushButton(acro_form)
    assert button_field.get_field_type() == button_field.get_cos_object().get_name(_FT)
    assert button_field.get_field_type() == "Btn"
    assert button_field.is_push_button() is True
    assert button_field.is_radio_button() is False


def test_create_radio_button(acro_form: PDAcroForm) -> None:
    """Upstream: ``createRadioButton``."""
    button_field = PDRadioButton(acro_form)
    assert button_field.get_field_type() == button_field.get_cos_object().get_name(_FT)
    assert button_field.get_field_type() == "Btn"
    assert button_field.is_radio_button() is True
    assert button_field.is_push_button() is False
