from __future__ import annotations

import logging

from pypdfbox.cos import (
    COSArray,
    COSDictionary,
    COSFloat,
    COSInteger,
    COSName,
    COSStream,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _parse_default_appearance,
    _rect_from_cos,
)
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_AP = COSName.get_pdf_name("AP")
_AS = COSName.get_pdf_name("AS")
_BBOX = COSName.get_pdf_name("BBox")
_DA = COSName.get_pdf_name("DA")
_MK = COSName.get_pdf_name("MK")
_N = COSName.get_pdf_name("N")
_OFF = COSName.get_pdf_name("Off")
_RECT = COSName.get_pdf_name("Rect")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


def _normal_body(field: object) -> bytes:
    widget_cos = field.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    return n.create_input_stream().read()


def test_constructor_default_appearance_override_drives_missing_da() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.set_value("override")

    PDAppearanceGenerator("/HeBo 9 Tf 0.25 g").generate(tf)

    body = _normal_body(tf)
    assert b"9 Tf" in body
    assert b"0.25 g" in body
    assert b"override" in body


def test_field_default_appearance_wins_over_generator_override() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 8 Tf 0 g")
    tf.set_value("field-da")

    PDAppearanceGenerator("/HeBo 11 Tf 0.5 g").generate(tf)

    body = _normal_body(tf)
    assert b"8 Tf" in body
    assert b"11 Tf" not in body


def test_generate_text_without_rect_logs_and_leaves_widget_unmodified(
    caplog,
) -> None:
    tf = PDTextField(PDAcroForm())
    tf.set_value("missing-rect")

    with caplog.at_level(logging.DEBUG):
        PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None
    assert "widget has no /Rect" in caplog.text


def test_generate_text_with_degenerate_rect_skips_appearance(
    caplog,
) -> None:
    tf = PDTextField(PDAcroForm())
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 0, 20))
    tf.set_value("zero-width")

    with caplog.at_level(logging.DEBUG):
        PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None
    assert "widget /Rect is degenerate" in caplog.text


def test_generate_unknown_terminal_field_logs_skip(caplog) -> None:
    from pypdfbox.pdmodel.interactive.form.pd_terminal_field import (
        PDFieldStub,
    )

    field = PDFieldStub(PDAcroForm())
    field.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))

    with caplog.at_level(logging.DEBUG):
        PDAppearanceGenerator().generate(field)

    assert field.get_cos_object().get_dictionary_object(_AP) is None
    assert "not a supported field type" in caplog.text


def test_generic_button_generates_checkbox_style_appearance() -> None:
    button = PDButton(PDAcroForm())
    button.get_cos_object().set_item(_RECT, _rect(0, 0, 16, 16))
    button.set_value("Yes")

    PDAppearanceGenerator().generate(button)

    widget_cos = button.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    assert isinstance(n, COSDictionary)
    assert isinstance(n.get_dictionary_object(COSName.get_pdf_name("Yes")), COSStream)
    assert isinstance(n.get_dictionary_object(_OFF), COSStream)
    assert widget_cos.get_name(_AS) == "Yes"


def test_button_missing_rect_does_not_install_appearance(caplog) -> None:
    cb = PDCheckBox(PDAcroForm())
    cb.set_value("Yes")

    with caplog.at_level(logging.DEBUG):
        PDAppearanceGenerator().generate(cb)

    widget_cos = cb.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None
    assert widget_cos.get_dictionary_object(_AS) is None
    assert "button widget has no /Rect" in caplog.text


def test_button_degenerate_rect_does_not_install_appearance() -> None:
    cb = PDCheckBox(PDAcroForm())
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 0))
    cb.set_value("Yes")

    PDAppearanceGenerator().generate(cb)

    widget_cos = cb.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None
    assert widget_cos.get_dictionary_object(_AS) is None


def test_push_button_background_and_border_colors_are_emitted() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton

    button = PDPushButton(PDAcroForm())
    cos = button.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 30))
    mk = COSDictionary()
    mk.set_string(COSName.get_pdf_name("CA"), "Go")
    mk.set_item(
        COSName.get_pdf_name("BG"),
        COSArray([COSFloat(0.1), COSFloat(0.2), COSFloat(0.3)]),
    )
    mk.set_item(
        COSName.get_pdf_name("BC"),
        COSArray([COSFloat(0.4), COSFloat(0.5), COSFloat(0.6)]),
    )
    cos.set_item(_MK, mk)

    PDAppearanceGenerator().generate(button)

    body = _normal_body(button)
    assert b"0.1 0.2 0.3 rg" in body
    assert b"0.4 0.5 0.6 RG" in body
    assert b"1 w" in body
    assert b"Go" in body


def test_push_button_without_rect_leaves_ap_absent() -> None:
    from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton

    button = PDPushButton(PDAcroForm())
    PDAppearanceGenerator().generate(button)

    assert button.get_cos_object().get_dictionary_object(_AP) is None


def test_rect_from_cos_accepts_integer_entries() -> None:
    arr = COSArray(
        [COSInteger(1), COSInteger(2), COSInteger(11), COSInteger(22)]
    )
    assert _rect_from_cos(arr) == (1.0, 2.0, 11.0, 22.0)


def test_parse_default_appearance_malformed_g_and_k_are_ignored() -> None:
    assert _parse_default_appearance("/Helv 10 Tf nope g")[2] is None
    assert _parse_default_appearance("/Helv 10 Tf 0 1 bad 0 k")[2] is None


def test_fresh_form_xobject_bbox_uses_requested_dimensions() -> None:
    stream = PDAppearanceGenerator._fresh_form_xobject(12.5, 7.25)

    bbox = stream.get_dictionary_object(_BBOX)
    assert isinstance(bbox, COSArray)
    assert [bbox.get_object(i).value for i in range(4)] == [
        0.0,
        0.0,
        12.5,
        7.25,
    ]
