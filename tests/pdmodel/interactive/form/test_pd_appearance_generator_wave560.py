from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.digitalsignature import PDSignature
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_AP = COSName.get_pdf_name("AP")
_AS = COSName.get_pdf_name("AS")
_DA = COSName.get_pdf_name("DA")
_MK = COSName.get_pdf_name("MK")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_RECT = COSName.get_pdf_name("Rect")
_V = COSName.get_pdf_name("V")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _normal_body(field: object) -> bytes:
    widget_cos = field.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    return n.create_input_stream().read()


def test_default_appearance_lookup_failure_uses_generator_override() -> None:
    class BrokenDATextField(PDTextField):
        def get_default_appearance(self) -> str | None:
            raise RuntimeError("bad inheritable lookup")

    field = BrokenDATextField(PDAcroForm())
    field.get_cos_object().set_item(_RECT, _rect(0, 0, 140, 24))
    field.set_value("fallback-da")

    PDAppearanceGenerator("/HeBo 9 Tf 0.25 g").generate(field)

    body = _normal_body(field)
    assert b"fallback-da" in body
    assert b"9 Tf" in body
    assert b"0.25 g" in body


def test_checkbox_preserves_existing_non_off_on_state_name() -> None:
    checkbox = PDCheckBox(PDAcroForm())
    cos = checkbox.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 18, 18))
    cos.set_name(_V, "Checked")
    existing_ap = COSDictionary()
    existing_normal = COSDictionary()
    existing_normal.set_item(_OFF, COSStream())
    existing_normal.set_item(COSName.get_pdf_name("Checked"), COSStream())
    existing_ap.set_item(_N, existing_normal)
    cos.set_item(_AP, existing_ap)

    PDAppearanceGenerator().generate(checkbox)

    normal = cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(normal, COSDictionary)
    assert isinstance(normal.get_dictionary_object(COSName.get_pdf_name("Checked")), COSStream)
    assert normal.get_dictionary_object(COSName.get_pdf_name("Yes")) is None
    assert cos.get_name(_AS) == "Checked"


def test_push_button_reuses_existing_appearance_dictionary() -> None:
    button = PDPushButton(PDAcroForm())
    cos = button.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 30))
    marker = COSName.get_pdf_name("Marker")
    existing_ap = COSDictionary()
    existing_ap.set_item(marker, COSName.get_pdf_name("KeepMe"))
    cos.set_item(_AP, existing_ap)
    mk = COSDictionary()
    mk.set_string(COSName.get_pdf_name("CA"), "Launch")
    cos.set_item(_MK, mk)

    PDAppearanceGenerator().generate(button)

    assert cos.get_dictionary_object(_AP) is existing_ap
    assert existing_ap.get_dictionary_object(marker).name == "KeepMe"
    assert b"Launch" in _normal_body(button)


def test_signed_signature_reuses_existing_appearance_dictionary() -> None:
    sig_field = PDSignatureField(PDAcroForm())
    cos = sig_field.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 180, 50))
    marker = COSName.get_pdf_name("Marker")
    existing_ap = COSDictionary()
    existing_ap.set_item(marker, COSName.get_pdf_name("KeepMe"))
    cos.set_item(_AP, existing_ap)
    signature = PDSignature()
    signature.set_name("Dana")
    sig_field.set_value(signature)

    PDAppearanceGenerator().generate(sig_field)

    assert cos.get_dictionary_object(_AP) is existing_ap
    assert existing_ap.get_dictionary_object(marker).name == "KeepMe"
    assert b"Dana" in _normal_body(sig_field)


def test_listbox_without_rect_leaves_appearance_absent() -> None:
    listbox = PDListBox(PDAcroForm())
    listbox.set_options(["alpha", "beta"])
    listbox.set_value("beta")

    PDAppearanceGenerator().generate(listbox)

    assert listbox.get_cos_object().get_dictionary_object(_AP) is None


def test_listbox_degenerate_rect_leaves_appearance_absent() -> None:
    listbox = PDListBox(PDAcroForm())
    listbox.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 0))
    listbox.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    listbox.set_options(["alpha", "beta"])
    listbox.set_value("beta")

    PDAppearanceGenerator().generate(listbox)

    assert listbox.get_cos_object().get_dictionary_object(_AP) is None
