from __future__ import annotations

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSName,
    COSStream,
    COSString,
)
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_signature_field import (
    PDSignatureField,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_AP = COSName.get_pdf_name("AP")
_DA = COSName.get_pdf_name("DA")
_N = COSName.get_pdf_name("N")
_RECT = COSName.get_pdf_name("Rect")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _normal_stream(field: object) -> COSStream:
    widget_cos = field.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    return n


def _normal_body(field: object) -> bytes:
    return _normal_stream(field).create_input_stream().read()


def test_combo_box_set_appearance_value_regenerates_visible_text() -> None:
    combo = PDComboBox(PDAcroForm())
    combo.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 20))
    combo.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    combo.set_options(["red", "green", "blue"])

    PDAppearanceGenerator().set_appearance_value(combo, "green")

    assert combo.get_value() == ["green"]
    body = _normal_body(combo)
    assert b"green" in body
    assert b"/Tx BMC" in body


def test_listbox_without_options_falls_back_to_selected_values() -> None:
    listbox = PDListBox(PDAcroForm())
    listbox.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 45))
    listbox.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    listbox.set_multi_select(True)
    listbox.set_value(["first", "second"])

    PDAppearanceGenerator().generate(listbox)

    body = _normal_body(listbox)
    assert b"first" in body
    assert b"second" in body
    assert body.count(b"Tj") == 2


def test_listbox_top_index_beyond_options_emits_no_rows() -> None:
    listbox = PDListBox(PDAcroForm())
    listbox.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 45))
    listbox.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    listbox.set_options(["one", "two"])
    listbox.set_top_index(10)

    PDAppearanceGenerator().generate(listbox)

    body = _normal_body(listbox)
    assert b"one" not in body
    assert b"two" not in body
    assert b"Tj" not in body
    assert b"/Tx BMC" in body


def test_listbox_negative_top_index_is_clamped_to_first_row() -> None:
    listbox = PDListBox(PDAcroForm())
    listbox.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 45))
    listbox.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    listbox.set_options(["zero", "one"])
    listbox.set_top_index(-5)

    PDAppearanceGenerator().generate(listbox)

    body = _normal_body(listbox)
    assert b"zero" in body
    assert b"one" in body


def test_choice_widget_without_rect_leaves_appearance_absent() -> None:
    combo = PDComboBox(PDAcroForm())
    combo.set_options(["alpha"])
    combo.set_value("alpha")

    PDAppearanceGenerator().generate(combo)

    assert combo.get_cos_object().get_dictionary_object(_AP) is None


def test_choice_widget_degenerate_rect_leaves_appearance_absent() -> None:
    combo = PDComboBox(PDAcroForm())
    combo.get_cos_object().set_item(_RECT, _rect(0, 0, 0, 20))
    combo.set_options(["alpha"])
    combo.set_value("alpha")

    PDAppearanceGenerator().generate(combo)

    assert combo.get_cos_object().get_dictionary_object(_AP) is None


def test_choice_option_lookup_failure_falls_back_to_selected_values() -> None:
    class BrokenOptionsListBox(PDListBox):
        def get_options_display_values(self) -> list[str]:
            raise RuntimeError("bad opt array")

        def get_options(self) -> list[str]:
            raise RuntimeError("bad opt array")

    listbox = BrokenOptionsListBox(PDAcroForm())
    listbox.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 45))
    listbox.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    listbox.get_cos_object().set_item(COSName.get_pdf_name("V"), COSString("fallback"))

    PDAppearanceGenerator().generate(listbox)

    body = _normal_body(listbox)
    assert b"fallback" in body


def test_existing_appearance_dictionary_is_reused_for_text_field() -> None:
    tf = PDTextField(PDAcroForm())
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 20))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    marker = COSName.get_pdf_name("Marker")
    existing_ap = COSDictionary()
    existing_ap.set_item(marker, COSName.get_pdf_name("KeepMe"))
    cos.set_item(_AP, existing_ap)
    tf.set_value("reuse")

    PDAppearanceGenerator().generate(tf)

    assert cos.get_dictionary_object(_AP) is existing_ap
    assert existing_ap.get_dictionary_object(marker).name == "KeepMe"
    assert b"reuse" in _normal_body(tf)


def test_signed_signature_with_date_emits_both_lines() -> None:
    sig_field = PDSignatureField(PDAcroForm())
    sig_field.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))
    signature = PDSignature()
    signature.set_name("Alice")
    signature.set_sign_date("D:20260508120000Z")
    sig_field.set_value(signature)

    PDAppearanceGenerator().generate(sig_field)

    body = _normal_body(sig_field)
    assert b"Alice" in body
    assert b"D:20260508120000Z" in body
    assert b"Sign here" not in body


def test_signature_with_only_date_is_treated_as_signed() -> None:
    sig_field = PDSignatureField(PDAcroForm())
    sig_field.get_cos_object().set_item(_RECT, _rect(0, 0, 200, 50))
    signature = PDSignature()
    signature.set_sign_date("D:20260508123000Z")
    sig_field.set_value(signature)

    PDAppearanceGenerator().generate(sig_field)

    body = _normal_body(sig_field)
    assert b"D:20260508123000Z" in body
    assert b"Sign here" not in body
    assert b"[3 3] 0 d" not in body


def test_signature_without_rect_leaves_appearance_absent() -> None:
    sig_field = PDSignatureField(PDAcroForm())

    PDAppearanceGenerator().generate(sig_field)

    assert sig_field.get_cos_object().get_dictionary_object(_AP) is None


def test_set_appearance_value_none_for_combo_clears_visible_text() -> None:
    combo = PDComboBox(PDAcroForm())
    combo.get_cos_object().set_item(_RECT, _rect(0, 0, 120, 20))
    combo.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    combo.set_options(["alpha"])
    combo.set_value("alpha")

    PDAppearanceGenerator().set_appearance_value(combo, None)

    assert combo.get_value() == []
    body = _normal_body(combo)
    assert b"alpha" not in body
    assert b"Tj" not in body
