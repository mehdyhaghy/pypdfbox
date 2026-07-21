"""Ported from upstream PDFBox 3.0 ``PDChoiceTest``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/PDChoiceTest.java``

Skipped upstream cases:
- ``PDFBox6150`` — depends on the external ``PDFBOX-6150.pdf`` regression
  fixture (see PDFBOX-6150) which is fetched by the upstream Maven harness
  from ``target/pdfs/``. Out of scope for this in-memory port. The behavior
  (combo appearance renders the DISPLAY value when export and display values
  differ, 3.0.8) is covered in-memory by
  ``tests/pdmodel/interactive/form/test_combo_display_value_wave1602.py``.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox

_FT: COSName = COSName.get_pdf_name("FT")
_OPT: COSName = COSName.get_pdf_name("Opt")


@pytest.fixture
def acro_form() -> PDAcroForm:
    return PDAcroForm()


@pytest.fixture
def options() -> list[str]:
    return [" ", "A", "B"]


def test_create_list_box(acro_form: PDAcroForm) -> None:
    """Upstream: ``createListBox``."""
    choice_field = PDListBox(acro_form)
    assert choice_field.get_field_type() == choice_field.get_cos_object().get_name(_FT)
    assert choice_field.get_field_type() == "Ch"
    assert choice_field.is_combo() is False


def test_create_combo_box(acro_form: PDAcroForm) -> None:
    """Upstream: ``createComboBox``."""
    choice_field = PDComboBox(acro_form)
    assert choice_field.get_field_type() == choice_field.get_cos_object().get_name(_FT)
    assert choice_field.get_field_type() == "Ch"
    assert choice_field.is_combo() is True


def test_get_options_from_strings(
    acro_form: PDAcroForm, options: list[str]
) -> None:
    """Upstream: ``getOptionsFromStrings`` — flat ``COSString`` array."""
    choice_field = PDComboBox(acro_form)
    choice_field_options = COSArray()
    choice_field_options.add(COSString(" "))
    choice_field_options.add(COSString("A"))
    choice_field_options.add(COSString("B"))
    choice_field.get_cos_object().set_item(_OPT, choice_field_options)
    assert choice_field.get_options() == options


def test_get_options_from_cos_array(
    acro_form: PDAcroForm, options: list[str]
) -> None:
    """Upstream: ``getOptionsFromCOSArray`` — single-element nested arrays."""
    choice_field = PDComboBox(acro_form)
    choice_field_options = COSArray()
    for value in (" ", "A", "B"):
        entry = COSArray()
        entry.add(COSString(value))
        choice_field_options.add(entry)
    choice_field.get_cos_object().set_item(_OPT, choice_field_options)
    assert choice_field.get_options() == options


def test_get_options_from_mixed(
    acro_form: PDAcroForm, options: list[str]
) -> None:
    """Upstream: ``getOptionsFromMixed`` — flat string then nested arrays."""
    choice_field = PDComboBox(acro_form)
    choice_field_options = COSArray()
    choice_field_options.add(COSString(" "))
    for value in ("A", "B"):
        entry = COSArray()
        entry.add(COSString(value))
        choice_field_options.add(entry)
    choice_field.get_cos_object().set_item(_OPT, choice_field_options)
    assert choice_field.get_options() == options
