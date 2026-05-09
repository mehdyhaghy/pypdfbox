from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.font.pd_font import PDFont
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField

_AP = COSName.get_pdf_name("AP")
_AS = COSName.get_pdf_name("AS")
_DA = COSName.get_pdf_name("DA")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_RECT = COSName.get_pdf_name("Rect")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _normal_body(field: object) -> bytes:
    widget_cos = field.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    return n.create_input_stream().read()


def test_checkbox_generate_without_matching_value_sets_appearance_state_off() -> None:
    checkbox = PDCheckBox(PDAcroForm())
    checkbox.get_cos_object().set_item(_RECT, _rect(0, 0, 18, 18))

    PDAppearanceGenerator().generate(checkbox)

    assert checkbox.get_cos_object().get_name(_AS) == "Off"


def test_radio_button_generation_uses_vector_dot_appearance() -> None:
    radio = PDRadioButton(PDAcroForm())
    radio.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    radio.set_value("Yes")

    PDAppearanceGenerator().generate(radio)

    normal = radio.get_cos_object().get_dictionary_object(_AP).get_dictionary_object(_N)
    on_stream = normal.get_dictionary_object(COSName.get_pdf_name("Yes"))
    assert isinstance(on_stream, COSStream)
    body = on_stream.create_input_stream().read()
    assert b" c\n" in body
    assert b"f\n" in body
    assert b"Tj" not in body


def test_combo_string_value_shape_renders_as_single_selected_line() -> None:
    class StringValueComboBox(PDComboBox):
        def get_value(self) -> str:
            return "manual"

    combo = StringValueComboBox(PDAcroForm())
    combo.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    combo.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")

    PDAppearanceGenerator().generate(combo)

    assert b"manual" in _normal_body(combo)


def test_combo_unknown_value_shape_reuses_existing_appearance_dictionary() -> None:
    class UnknownValueComboBox(PDComboBox):
        def get_value(self) -> object:
            return object()

    combo = UnknownValueComboBox(PDAcroForm())
    cos = combo.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 100, 20))
    marker = COSName.get_pdf_name("Marker")
    existing_ap = COSDictionary()
    existing_ap.set_item(marker, COSName.get_pdf_name("KeepMe"))
    cos.set_item(_AP, existing_ap)

    PDAppearanceGenerator().generate(combo)

    assert cos.get_dictionary_object(_AP) is existing_ap
    assert existing_ap.get_dictionary_object(marker).name == "KeepMe"
    assert b"Tj" not in _normal_body(combo)


def test_combo_multiple_selected_values_emit_multiple_lines() -> None:
    class MultiValueComboBox(PDComboBox):
        def get_value(self) -> list[str]:
            return ["red", "green"]

    combo = MultiValueComboBox(PDAcroForm())
    combo.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 40))
    combo.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    combo.set_options(["red", "green", "blue"])

    PDAppearanceGenerator().generate(combo)

    body = _normal_body(combo)
    assert b"red" in body
    assert b"green" in body
    assert body.count(b"Tj") == 2


def test_listbox_without_da_defaults_to_black_text_and_reuses_ap_dict() -> None:
    listbox = PDListBox(PDAcroForm())
    cos = listbox.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 45))
    marker = COSName.get_pdf_name("Marker")
    existing_ap = COSDictionary()
    existing_ap.set_item(marker, COSName.get_pdf_name("KeepMe"))
    cos.set_item(_AP, existing_ap)
    listbox.set_options(["alpha", "beta"])

    PDAppearanceGenerator().generate(listbox)

    assert cos.get_dictionary_object(_AP) is existing_ap
    assert existing_ap.get_dictionary_object(marker).name == "KeepMe"
    body = _normal_body(listbox)
    assert b"0 g" in body
    assert b"alpha" in body


def test_push_button_degenerate_rect_leaves_appearance_absent() -> None:
    button = PDPushButton(PDAcroForm())
    button.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 0))

    PDAppearanceGenerator().generate(button)

    assert button.get_cos_object().get_dictionary_object(_AP) is None


def test_signature_degenerate_rect_leaves_appearance_absent() -> None:
    sig_field = PDSignatureField(PDAcroForm())
    sig_field.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 0))

    PDAppearanceGenerator().generate(sig_field)

    assert sig_field.get_cos_object().get_dictionary_object(_AP) is None


def test_estimate_text_width_uses_half_em_fallback_for_zero_average_font() -> None:
    class ZeroAverageWidthFont(PDFont):
        def get_average_font_width(self) -> float:
            return 0.0

    width = PDAppearanceGenerator._estimate_text_width(
        ZeroAverageWidthFont(), 12.0, "AB"
    )

    assert width == 12.0
