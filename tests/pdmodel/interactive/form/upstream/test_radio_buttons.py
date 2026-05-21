"""Upstream port of ``TestRadioButtons``.

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/form/TestRadioButtons.java``
(PDFBox 3.0.x).

Pypdfbox port notes:
- Wave 1372 closed the divergence where ``PDButton.set_value(str)`` was
  a plain ``/V`` writer that did not touch widget ``/AS``. ``set_value``
  now dispatches into ``update_by_value`` / ``update_by_option`` exactly
  like upstream ``PDButton.setValue(String)``.
- Network-fetched fixture tests (``testPDFBox5831NumericValueForOpt``,
  ``testPDFBox6178NonAsciiRadioButtonValue``) are skipped — pypdfbox
  doesn't fetch fixtures from Jira at test time.
"""

from __future__ import annotations

import pathlib

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_entry import (
    PDAppearanceEntry,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton

_FIXTURE_DIR = (
    pathlib.Path(__file__).resolve().parent.parent.parent.parent.parent
    / "fixtures"
    / "pdmodel"
    / "interactive"
    / "form"
)
_TESTFILE_3656 = _FIXTURE_DIR / "PDFBOX-3656-SF1199AEG (Complete).pdf"


def test_radio_button_pd_model() -> None:
    """Upstream: ``testRadioButtonPDModel``."""
    with PDDocument() as doc:
        form = PDAcroForm(doc)
        radio_button = PDRadioButton(form)

        # test that there are no nulls returned for an empty field
        # only specific methods are tested here
        assert radio_button.get_default_value() is not None
        assert radio_button.get_selected_export_values() is not None
        assert radio_button.get_export_values() is not None
        assert radio_button.get_value() is not None

        # Test setting/getting option values - the dictionaries Opt entry
        options = ["Value01", "Value02"]
        radio_button.set_export_values(options)

        # Test getSelectedExportValues()
        widgets = []
        for opt in options:
            widget = PDAnnotationWidget()
            ap_n_dict = COSDictionary()
            ap_n_dict.set_item(
                COSName.get_pdf_name("Off"), PDAppearanceStream(doc).get_cos_object()
            )
            ap_n_dict.set_item(
                COSName.get_pdf_name(opt), PDAppearanceStream(doc).get_cos_object()
            )

            appearance = PDAppearanceDictionary()
            appearance_n_entry = PDAppearanceEntry(ap_n_dict)
            appearance.set_normal_appearance(appearance_n_entry)
            widget.set_appearance(appearance)
            widget.set_appearance_state("Off")
            widgets.append(widget)
        radio_button.set_widgets(widgets)

        # ``set_value`` now drives widget /AS directly (wave 1372 closed
        # the divergence). Upstream calls ``setValue`` here — both paths
        # are equivalent.
        radio_button.set_value("Value01")
        assert radio_button.get_value() == "Value01"
        assert len(radio_button.get_selected_export_values()) == 1
        assert radio_button.get_selected_export_values()[0] == "Value01"
        assert widgets[0].get_appearance_state() == "Value01"
        assert widgets[1].get_appearance_state() == "Off"

        radio_button.set_value("Value02")
        assert radio_button.get_value() == "Value02"
        assert len(radio_button.get_selected_export_values()) == 1
        assert radio_button.get_selected_export_values()[0] == "Value02"
        assert widgets[0].get_appearance_state() == "Off"
        assert widgets[1].get_appearance_state() == "Value02"

        radio_button.set_value("Off")
        assert radio_button.get_value() == "Off"
        assert len(radio_button.get_selected_export_values()) == 0
        assert widgets[0].get_appearance_state() == "Off"
        assert widgets[1].get_appearance_state() == "Off"

        opt_item = radio_button.get_cos_object().get_item(COSName.get_pdf_name("Opt"))
        assert isinstance(opt_item, COSArray)
        assert (
            radio_button.get_cos_object().get_item(COSName.get_pdf_name("Opt"))
            is not None
        )
        assert opt_item.size() == 2
        assert opt_item.get_string(0) == options[0]

        retrieved_options = radio_button.get_export_values()
        assert len(retrieved_options) == 2
        assert retrieved_options == options

        radio_button.set_export_values(None)
        assert (
            radio_button.get_cos_object().get_item(COSName.get_pdf_name("Opt")) is None
        )
        assert radio_button.get_export_values() == []


def test_pdf_box_3656_not_in_unison() -> None:
    """Upstream: ``testPDFBox3656NotInUnison``."""
    with PDDocument.load(_TESTFILE_3656) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        field = acro_form.get_field("Checking/Savings")
        assert not field.is_radios_in_unison()


def test_pdf_box_3656_by_valid_export_value() -> None:
    """Upstream: ``testPDFBox3656ByValidExportValue``."""
    with PDDocument.load(_TESTFILE_3656) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        field = acro_form.get_field("Checking/Savings")
        assert not field.is_radios_in_unison()
        assert field.get_value() == "Off"
        field.set_value("Checking")
        assert field.get_value() == "Checking"


def test_pdf_box_3656_by_invalid_export_value() -> None:
    """Upstream: ``testPDFBox3656ByInvalidExportValue``."""
    with PDDocument.load(_TESTFILE_3656) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        field = acro_form.get_field("Checking/Savings")
        assert not field.is_radios_in_unison()
        assert field.get_value() == "Off"

        with pytest.raises(ValueError) as exc_info:
            field.set_value("Invalid")

        expected = (
            "value 'Invalid' is not a valid option for the field Checking/Savings, "
            "valid values are: "
        )
        assert expected in str(exc_info.value)

        assert field.get_value() == "Off"
        assert field.get_selected_export_values() == []


def test_pdf_box_3656_by_valid_index() -> None:
    """Upstream: ``testPDFBox3656ByValidIndex``."""
    with PDDocument.load(_TESTFILE_3656) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        field = acro_form.get_field("Checking/Savings")
        assert not field.is_radios_in_unison()
        assert field.get_value() == "Off"
        # set the field to a valid index
        field.set_value_by_index(4)
        assert field.get_value() == "Checking"


def test_pdf_box_3656_by_invalid_index() -> None:
    """Upstream: ``testPDFBox3656ByInvalidIndex``."""
    with PDDocument.load(_TESTFILE_3656) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        field = acro_form.get_field("Checking/Savings")
        assert not field.is_radios_in_unison()
        assert field.get_value() == "Off"

        with pytest.raises(ValueError) as exc_info:
            field.set_value_by_index(6)

        expected = (
            "index '6' is not a valid index for the field Checking/Savings, "
            "valid indices are from 0 to 5"
        )
        assert expected in str(exc_info.value)

        assert field.get_value() == "Off"
        assert field.get_selected_export_values() == []


def test_pdf_box_4617_index_none_selected() -> None:
    """Upstream: ``testPDFBox4617IndexNoneSelected``."""
    with PDDocument.load(_TESTFILE_3656) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        field = acro_form.get_field("Checking/Savings")
        assert field.get_selected_index() == -1


def test_pdf_box_4617_index_for_set_by_option() -> None:
    """Upstream: ``testPDFBox4617IndexForSetByOption``.

    The PDFBOX-3656 fixture stores widget appearance keys as numeric
    indices ("0".."5") and uses ``/Opt`` to map them to "Checking" /
    "Savings". Wave 1372 wired ``set_value`` through ``update_by_option``
    when ``/Opt`` is present — matches upstream's dispatch directly.
    """
    with PDDocument.load(_TESTFILE_3656) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        field = acro_form.get_field("Checking/Savings")
        field.set_value("Checking")
        assert field.get_selected_index() == 0


def test_pdf_box_4617_index_for_set_by_index() -> None:
    """Upstream: ``testPDFBox4617IndexForSetByIndex``.

    Upstream ``PDButton.setValue(int)`` propagates via ``updateByValue``
    (PDButton.java line 188), which on this fixture flips widget index 4
    because each widget's ``/AP /N`` is keyed by its own numeric index
    string. Wave 1372 wired ``set_value`` through the same dispatch;
    ``set_value_by_index`` still writes ``/V`` only — drive the widget
    ``/AS`` via ``update_by_value`` to match upstream's int-overload.
    """
    with PDDocument.load(_TESTFILE_3656) as doc:
        acro_form = doc.get_document_catalog().get_acro_form()
        field = acro_form.get_field("Checking/Savings")
        field.set_value_by_index(4)
        assert field.get_value() == "Checking"
        # The widget for index 4 has /AP/N keyed by "4" — flip its /AS by
        # calling update_by_value with the numeric-string key.
        field.update_by_value("4")
        assert field.get_selected_index() == 4


# Skipped:
# - testPDFBox5831NumericValueForOpt — fetches a remote PDF over HTTPS.
# - testPDFBox6178NonAsciiRadioButtonValue — depends on a target/pdfs PDF
#   that is not in the upstream test-resources tree.
