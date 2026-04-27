from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_dictionary import (
    PDAppearanceDictionary,
)
from pypdfbox.pdmodel.interactive.annotation.pd_appearance_stream import (
    PDAppearanceStream,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_appearance_generator import (
    _parse_default_appearance,
)
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_RECT: COSName = COSName.get_pdf_name("Rect")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_DA: COSName = COSName.get_pdf_name("DA")
_BBOX: COSName = COSName.get_pdf_name("BBox")
_TYPE: COSName = COSName.get_pdf_name("Type")
_SUBTYPE: COSName = COSName.get_pdf_name("Subtype")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


# ---------- /DA parser ----------


def test_parse_default_appearance_full() -> None:
    name, size, color = _parse_default_appearance("/Helv 12 Tf 0 0 0 rg")
    assert name == "Helv"
    assert size == 12.0
    assert color == (0.0, 0.0, 0.0)


def test_parse_default_appearance_grayscale() -> None:
    name, size, color = _parse_default_appearance("/HeBo 10 Tf 0.5 g")
    assert name == "HeBo"
    assert size == 10.0
    assert color == (0.5,)


def test_parse_default_appearance_cmyk() -> None:
    name, size, color = _parse_default_appearance("/TiRo 14 Tf 0 1 1 0 k")
    assert name == "TiRo"
    assert size == 14.0
    assert color == (0.0, 1.0, 1.0, 0.0)


def test_parse_default_appearance_empty() -> None:
    assert _parse_default_appearance(None) == (None, 0.0, None)
    assert _parse_default_appearance("") == (None, 0.0, None)


def test_parse_default_appearance_auto_size() -> None:
    name, size, _ = _parse_default_appearance("/Helv 0 Tf 0 g")
    assert name == "Helv"
    assert size == 0.0


# ---------- generator end-to-end ----------


def _build_text_field(value: str = "hello") -> PDTextField:
    form = PDAcroForm()
    tf = PDTextField(form)
    cos = tf.get_cos_object()
    cos.set_item(_RECT, _rect(50.0, 700.0, 250.0, 720.0))
    cos.set_string(_DA, "/Helv 12 Tf 0 0 0 rg")
    tf.set_value(value)
    return tf


def test_generate_creates_normal_appearance() -> None:
    tf = _build_text_field("hello world")
    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n_entry = ap.get_dictionary_object(_N)
    assert isinstance(n_entry, COSStream)


def test_generate_appearance_stream_carries_value_text() -> None:
    tf = _build_text_field("hello world")
    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = PDAppearanceDictionary(widget_cos.get_dictionary_object(_AP))
    n_entry = ap.get_normal_appearance()
    assert n_entry is not None
    n_cos = n_entry.get_cos_object()
    assert isinstance(n_cos, COSStream)

    # Wrap as appearance stream so we can read the body.
    stream = PDAppearanceStream(n_cos)
    body = stream.get_stream().create_input_stream().read()
    assert b"BT" in body
    assert b"ET" in body
    assert b"hello world" in body
    # Tf operator emitted with the resolved size.
    assert b"Tf" in body
    # /Tx BMC marker — Acrobat looks for this on form-field appearances.
    assert b"/Tx BMC" in body
    assert b"EMC" in body


def test_generate_sets_form_xobject_metadata() -> None:
    tf = _build_text_field()
    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    assert n.get_name(_TYPE) == "XObject"
    assert n.get_name(_SUBTYPE) == "Form"
    bbox = n.get_dictionary_object(_BBOX)
    assert isinstance(bbox, COSArray)
    assert bbox.size() == 4
    # bbox is [0 0 width height] of the Rect (200 x 20).
    floats = [bbox.get_object(i).value for i in range(4)]
    assert floats[0] == 0.0
    assert floats[1] == 0.0
    assert abs(floats[2] - 200.0) < 1e-6
    assert abs(floats[3] - 20.0) < 1e-6


def test_generate_skips_non_text_fields() -> None:
    """Non-text fields are deferred — generator silently skips them."""
    from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    PDAppearanceGenerator().generate(cb)
    # No /AP installed on the widget.
    widget_cos = cb.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None


def test_generate_empty_value_emits_no_text_string_but_keeps_stream() -> None:
    tf = _build_text_field("")
    PDAppearanceGenerator().generate(tf)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    body = n.create_input_stream().read()
    # BT/ET still emitted; show-text operator is skipped because value is "".
    assert b"BT" in body
    assert b"ET" in body
    # No "Tj" without a value.
    assert b"Tj" not in body


def test_generate_handles_missing_da_with_helvetica_fallback() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.set_value("x")
    # No /DA set anywhere — generator falls back to Helvetica auto-size.
    PDAppearanceGenerator().generate(tf)
    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)


# ---------- set_value(regenerate_appearance=...) wiring ----------


def test_set_value_regenerate_appearance_false_does_not_create_ap() -> None:
    tf = _build_text_field()
    # Strip any /AP that might already be on the widget; default path
    # should keep it that way.
    tf.get_cos_object().remove_item(_AP)
    tf.set_value("changed")
    assert tf.get_cos_object().get_dictionary_object(_AP) is None


def test_set_value_regenerate_appearance_true_creates_ap() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_value("changed", regenerate_appearance=True)

    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    body = n.create_input_stream().read()
    assert b"changed" in body


def test_set_value_clear_with_regenerate_appearance() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 20))
    tf.get_cos_object().set_string(_DA, "/Helv 10 Tf 0 g")
    tf.set_value("first", regenerate_appearance=True)
    tf.set_value(None, regenerate_appearance=True)

    # After clearing, /AP /N is rewritten with empty body (no Tj).
    widget_cos = tf.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"Tj" not in body
