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

Additional coverage for the upstream private helpers
(``getOnValue(int)``, ``getOnValueForWidget``, ``updateByValue``,
``updateByOption``, ``findMatchingAppearanceKey``) that have been promoted
to package-visible methods on ``PDButton`` for parity bookkeeping is
included below — these validate the behaviour rather than test access.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation import PDAnnotationWidget
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton

_AP = COSName.get_pdf_name("AP")
_AS = COSName.get_pdf_name("AS")
_FT: COSName = COSName.get_pdf_name("FT")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_V = COSName.get_pdf_name("V")


def _widget_with_states(*states: str) -> PDAnnotationWidget:
    normal = COSDictionary()
    for state in states:
        # On-value discovery filters to COSStream-valued state keys via
        # PDAppearanceEntry.get_sub_dictionary() (wave 1488, mirroring
        # upstream's getOnValueForWidget through getSubDictionary).
        normal.set_item(COSName.get_pdf_name(state), COSStream())
    ap = COSDictionary()
    ap.set_item(_N, normal)
    widget = PDAnnotationWidget()
    widget.get_cos_object().set_item(_AP, ap)
    return widget


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


# ---------- helpers ported alongside upstream private methods ----------


def test_get_on_value_for_widget_returns_first_non_off_key(
    acro_form: PDAcroForm,
) -> None:
    """Mirrors ``PDButton.getOnValueForWidget`` (private, line 353)."""
    widget = _widget_with_states("Off", "Yes")
    assert PDButton.get_on_value_for_widget(widget) == "Yes"


def test_get_on_value_for_widget_returns_empty_when_only_off(
    acro_form: PDAcroForm,
) -> None:
    widget = _widget_with_states("Off")
    assert PDButton.get_on_value_for_widget(widget) == ""


def test_get_on_value_for_widget_returns_empty_without_appearance(
    acro_form: PDAcroForm,
) -> None:
    widget = PDAnnotationWidget()
    assert PDButton.get_on_value_for_widget(widget) == ""


def test_get_on_value_at_index_returns_widget_on_value(
    acro_form: PDAcroForm,
) -> None:
    """Mirrors ``PDButton.getOnValue(int)`` (private, line 340)."""
    button = PDCheckBox(acro_form)
    button.set_widgets([_widget_with_states("On1"), _widget_with_states("On2")])
    assert button.get_on_value_at_index(0) == "On1"
    assert button.get_on_value_at_index(1) == "On2"
    # Index out of range yields "" per upstream
    assert button.get_on_value_at_index(2) == ""


def test_find_matching_appearance_key_returns_exact_cosname(
    acro_form: PDAcroForm,
) -> None:
    """Mirrors ``PDButton.findMatchingAppearanceKey`` (private, line 452)."""
    appearance = COSDictionary()
    yes = COSName.get_pdf_name("Yes")
    appearance.set_item(yes, COSDictionary())
    appearance.set_item(_OFF, COSDictionary())

    match = PDButton.find_matching_appearance_key(appearance, "Yes")
    assert match is yes

    assert PDButton.find_matching_appearance_key(appearance, "No") is None


def test_update_by_value_sets_widget_as_and_field_v(
    acro_form: PDAcroForm,
) -> None:
    """Mirrors ``PDButton.updateByValue`` (private, line 391)."""
    button = PDCheckBox(acro_form)
    widget = _widget_with_states("Yes", "Off")
    button.set_widgets([widget])

    button.update_by_value("Yes")

    assert widget.get_cos_object().get_name(_AS) == "Yes"
    assert button.get_cos_object().get_name(_V) == "Yes"


def test_update_by_value_falls_back_to_off_when_no_match(
    acro_form: PDAcroForm,
) -> None:
    button = PDCheckBox(acro_form)
    widget = _widget_with_states("Yes", "Off")
    button.set_widgets([widget])

    button.update_by_value("Nope")

    # Per upstream: per-widget fallback to /Off, /V written to the raw value
    assert widget.get_cos_object().get_name(_AS) == "Off"
    assert button.get_cos_object().get_name(_V) == "Nope"


def test_update_by_option_requires_widget_count_to_match_options(
    acro_form: PDAcroForm,
) -> None:
    """Mirrors ``PDButton.updateByOption`` (private, line 466)."""
    button = PDCheckBox(acro_form)
    button.set_widgets([_widget_with_states("On1")])
    button.set_export_values(["a", "b"])

    with pytest.raises(ValueError, match="number of options"):
        button.update_by_option("a")


def test_update_by_option_off_short_circuits_to_update_by_value(
    acro_form: PDAcroForm,
) -> None:
    button = PDCheckBox(acro_form)
    widget = _widget_with_states("Yes", "Off")
    button.set_widgets([widget])
    button.set_export_values(["only"])

    button.update_by_option("Off")

    assert widget.get_cos_object().get_name(_AS) == "Off"
    assert button.get_cos_object().get_name(_V) == "Off"


def test_update_by_option_resolves_index_to_widget_on_value(
    acro_form: PDAcroForm,
) -> None:
    button = PDCheckBox(acro_form)
    button.set_widgets([_widget_with_states("first"), _widget_with_states("second")])
    button.set_export_values(["alpha", "beta"])

    button.update_by_option("beta")

    # The on-value for widget at index 1 is "second" — that's what gets
    # propagated as the field value via update_by_value.
    assert button.get_cos_object().get_name(_V) == "second"
