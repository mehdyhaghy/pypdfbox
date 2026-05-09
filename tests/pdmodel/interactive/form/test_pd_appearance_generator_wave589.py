from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.interactive.form.pd_variable_text import PDVariableText

_AP = COSName.get_pdf_name("AP")
_MK = COSName.get_pdf_name("MK")
_N = COSName.get_pdf_name("N")
_RECT = COSName.get_pdf_name("Rect")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray([COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)])


def _normal_body(field: object) -> bytes:
    widget_cos = field.get_widgets()[0].get_cos_object()
    normal = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(normal, COSStream)
    return normal.create_input_stream().read()


def test_wave589_set_appearance_value_collapses_single_line_newline_classes() -> None:
    field = PDTextField(PDAcroForm())
    field.get_cos_object().set_item(_RECT, _rect(0, 0, 160, 24))

    PDAppearanceGenerator().set_appearance_value(field, "a\r\nb\u2028c\u2029d")

    assert field.get_value() == "a b c d"
    body = _normal_body(field)
    assert b"a b c d" in body
    assert b"\r\nb" not in body


def test_wave589_set_appearance_value_multiline_preserves_line_breaks() -> None:
    field = PDTextField(PDAcroForm())
    field.set_multiline(True)
    field.get_cos_object().set_item(_RECT, _rect(0, 0, 160, 48))

    PDAppearanceGenerator().set_appearance_value(field, "alpha\nbeta")

    assert field.get_value() == "alpha\nbeta"
    body = _normal_body(field)
    assert b"alpha" in body
    assert b"beta" in body


def test_wave589_unsupported_variable_text_field_is_not_supported_or_rendered() -> None:
    class CustomVariableText(PDVariableText):
        pass

    field = CustomVariableText(PDAcroForm(), COSDictionary())
    assert PDAppearanceGenerator.is_supported_field(field) is False

    PDAppearanceGenerator().generate(field)

    assert field.get_cos_object().get_dictionary_object(_AP) is None


def test_wave589_button_without_rect_leaves_appearance_absent() -> None:
    checkbox = PDCheckBox(PDAcroForm())

    PDAppearanceGenerator().generate(checkbox)

    assert checkbox.get_cos_object().get_dictionary_object(_AP) is None


def test_wave589_reversed_widget_rect_normalizes_bbox_dimensions() -> None:
    field = PDTextField(PDAcroForm())
    field.get_cos_object().set_item(_RECT, _rect(100, 20, 0, 0))
    field.set_value("normalized")

    PDAppearanceGenerator().generate(field)

    widget_cos = field.get_widgets()[0].get_cos_object()
    normal = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(normal, COSStream)
    bbox = normal.get_dictionary_object(COSName.get_pdf_name("BBox"))
    assert isinstance(bbox, COSArray)
    assert bbox.get_object(2).value == 100.0
    assert bbox.get_object(3).value == 20.0
    assert b"normalized" in normal.create_input_stream().read()


def test_wave589_push_button_ignores_malformed_mk_colors_but_renders_caption() -> None:
    button = PDPushButton(PDAcroForm())
    cos = button.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 30))
    mk = COSDictionary()
    mk.set_string(COSName.get_pdf_name("CA"), "Submit")
    mk.set_item(COSName.get_pdf_name("BG"), COSArray([COSFloat(0.1), COSName.get_pdf_name("bad")]))
    mk.set_item(COSName.get_pdf_name("BC"), COSArray([COSFloat(0.1), COSFloat(0.2)]))
    cos.set_item(_MK, mk)

    PDAppearanceGenerator().generate(button)

    body = _normal_body(button)
    assert b"Submit" in body
    assert b" re\nf\n" not in body
    assert b" re\nS\n" not in body


def test_wave589_unsigned_signature_renders_dashed_placeholder() -> None:
    sig_field = PDSignatureField(PDAcroForm())
    sig_field.get_cos_object().set_item(_RECT, _rect(0, 0, 180, 50))

    PDAppearanceGenerator().generate(sig_field)

    body = _normal_body(sig_field)
    assert b"[3 3] 0 d" in body
    assert b"[] 0 d" in body
    assert b"Sign here" in body
