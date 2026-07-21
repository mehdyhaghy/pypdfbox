"""PDFBOX-6150 (upstream 3.0.8): combo box appearance uses the DISPLAY value.

Upstream ``PDComboBox.constructAppearances`` renders the entry of the options
DISPLAY list at the index of the selected export value within the options
EXPORT list whenever the field carries separate export and display values.
When the export value is not found in the options, the raw ``/V`` export
value is rendered unchanged.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox

_AP = COSName.get_pdf_name("AP")
_DA = COSName.get_pdf_name("DA")
_N = COSName.get_pdf_name("N")
_RECT = COSName.get_pdf_name("Rect")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _normal_body(field: PDComboBox) -> bytes:
    widget_cos = field.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    return n.create_input_stream().read()


def _make_combo() -> PDComboBox:
    combo = PDComboBox(PDAcroForm())
    combo.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 20))
    combo.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    return combo


def test_combo_with_separate_display_values_renders_display_string() -> None:
    """Export != display: the appearance stream shows the display half."""
    combo = _make_combo()
    combo.set_options(["DE", "FR"], ["Deutschland", "Frankreich"])

    combo.set_value("DE")

    assert combo.get_value() == ["DE"]
    body = _normal_body(combo)
    assert b"Deutschland" in body
    assert b"(DE)" not in body


def test_combo_with_flat_options_renders_export_value_unchanged() -> None:
    """Export == display (flat /Opt strings): behavior unchanged."""
    combo = _make_combo()
    combo.set_options(["red", "green", "blue"])

    combo.set_value("green")

    body = _normal_body(combo)
    assert b"green" in body


def test_combo_value_not_in_options_falls_back_to_export_value() -> None:
    """A /V not present in the export list renders the raw export value —
    mirrors upstream's ``index == -1`` fallthrough."""
    combo = _make_combo()
    combo.set_options(["DE", "FR"], ["Deutschland", "Frankreich"])

    # Upstream PDChoice.setValue(String) performs no membership check.
    combo.set_value("XX")

    body = _normal_body(combo)
    assert b"XX" in body
    assert b"Deutschland" not in body
    assert b"Frankreich" not in body


def test_combo_display_mapping_applies_on_construct_appearances() -> None:
    """``construct_appearances`` (the upstream entry point) applies the same
    display mapping when /V was written without appearance regeneration."""
    combo = _make_combo()
    combo.set_options(["DE", "FR"], ["Deutschland", "Frankreich"])
    combo.get_cos_object().set_string(COSName.get_pdf_name("V"), "FR")

    combo.construct_appearances()

    body = _normal_body(combo)
    assert b"Frankreich" in body
    assert b"(FR)" not in body


def test_combo_second_export_value_maps_to_second_display_value() -> None:
    combo = _make_combo()
    combo.set_options(["e1", "e2", "e3"], ["one", "two", "three"])

    PDAppearanceGenerator().set_appearance_value(combo, "e2")

    body = _normal_body(combo)
    assert b"two" in body
    assert b"(e2)" not in body
