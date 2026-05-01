from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSFloat, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm, PDAppearanceGenerator
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton

_RECT: COSName = COSName.get_pdf_name("Rect")
_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_AS: COSName = COSName.get_pdf_name("AS")
_OFF: COSName = COSName.get_pdf_name("Off")
_DA: COSName = COSName.get_pdf_name("DA")


def _rect(llx: float, lly: float, urx: float, ury: float) -> COSArray:
    return COSArray(
        [COSFloat(llx), COSFloat(lly), COSFloat(urx), COSFloat(ury)]
    )


# ---------- check box ----------


def test_check_box_generate_creates_two_state_subdict() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))

    PDAppearanceGenerator().generate(cb)

    widget_cos = cb.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSDictionary)
    # Both /Yes and /Off entries present.
    keys = {k.name for k in n.key_set()}
    assert "Yes" in keys
    assert "Off" in keys
    # Each entry is a form-XObject content stream.
    yes_stream = n.get_dictionary_object(COSName.get_pdf_name("Yes"))
    off_stream = n.get_dictionary_object(_OFF)
    assert isinstance(yes_stream, COSStream)
    assert isinstance(off_stream, COSStream)


def test_check_box_on_state_stream_emits_check_glyph() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    PDAppearanceGenerator().generate(cb)

    widget_cos = cb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    yes_stream = n.get_dictionary_object(COSName.get_pdf_name("Yes"))
    body = yes_stream.create_input_stream().read()
    # Text-show operator is emitted with the ZapfDingbats check code.
    assert b"BT" in body
    assert b"ET" in body
    assert b"Tj" in body
    # The check glyph encoding ('4' literal) appears in the stream.
    assert b"(4)" in body


def test_check_box_off_state_stream_is_empty_form_xobject() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    PDAppearanceGenerator().generate(cb)

    widget_cos = cb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    off_stream = n.get_dictionary_object(_OFF)
    body = off_stream.create_input_stream().read()
    # Empty body — no text or path operators.
    assert b"Tj" not in body
    assert b"BT" not in body


def test_check_box_set_value_regenerate_appearance_syncs_as() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))

    cb.set_value("Yes", regenerate_appearance=True)
    widget_cos = cb.get_widgets()[0].get_cos_object()
    assert widget_cos.get_name(_AS) == "Yes"

    cb.set_value("Off", regenerate_appearance=True)
    assert widget_cos.get_name(_AS) == "Off"


def test_check_box_set_value_no_regenerate_skips_ap() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))
    cb.set_value("Yes")
    widget_cos = cb.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None


def test_check_box_construct_appearances_syncs_existing_ap_only() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    widget_cos = cb.get_cos_object()
    ap = COSDictionary()
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSStream())
    n.set_item(_OFF, COSStream())
    ap.set_item(_N, n)
    widget_cos.set_item(_AP, ap)
    cb.set_value("Yes")

    cb.construct_appearances()

    assert widget_cos.get_name(_AS) == "Yes"


def test_check_box_preserves_existing_on_state_name() -> None:
    """Re-running generation keeps a non-default on-state name (/Custom)."""
    form = PDAcroForm()
    cb = PDCheckBox(form)
    widget_cos = cb.get_cos_object()
    widget_cos.set_item(_RECT, _rect(0, 0, 20, 20))
    # Pre-seed an /AP with a custom on-state name.
    ap = COSDictionary()
    n = COSDictionary()
    fake_stream = COSStream()
    n.set_item(COSName.get_pdf_name("Custom"), fake_stream)
    n.set_item(_OFF, COSStream())
    ap.set_item(_N, n)
    widget_cos.set_item(_AP, ap)

    PDAppearanceGenerator().generate(cb)

    new_n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    keys = {k.name for k in new_n.key_set()}
    assert "Custom" in keys
    assert "Off" in keys


# ---------- radio button ----------


def test_radio_button_generate_creates_two_state_subdict() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))

    PDAppearanceGenerator().generate(rb)

    widget_cos = rb.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    keys = {k.name for k in n.key_set()}
    assert "Yes" in keys
    assert "Off" in keys


def test_radio_button_on_state_stream_emits_filled_circle() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))

    PDAppearanceGenerator().generate(rb)

    widget_cos = rb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    yes_stream = n.get_dictionary_object(COSName.get_pdf_name("Yes"))
    body = yes_stream.create_input_stream().read()
    # Path operators for the inscribed circle: m + c (cubic) + h + f (fill).
    assert b" m\n" in body
    assert b" c\n" in body
    assert b"h\n" in body
    assert b"f\n" in body
    # No text show — radios use a vector path, not a glyph.
    assert b"Tj" not in body


def test_radio_button_set_value_regenerate_appearance() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.get_cos_object().set_item(_RECT, _rect(0, 0, 20, 20))

    rb.set_value("Yes", regenerate_appearance=True)
    widget_cos = rb.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    assert widget_cos.get_name(_AS) == "Yes"


def test_radio_button_construct_appearances_syncs_existing_ap_only() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    widget_cos = rb.get_cos_object()
    ap = COSDictionary()
    n = COSDictionary()
    n.set_item(COSName.get_pdf_name("Yes"), COSStream())
    n.set_item(_OFF, COSStream())
    ap.set_item(_N, n)
    widget_cos.set_item(_AP, ap)
    rb.set_value("Yes")

    rb.construct_appearances()

    assert widget_cos.get_name(_AS) == "Yes"


# ---------- push button (skipped) ----------


def test_push_button_generate_emits_caption_stream() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    pb.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 30))

    PDAppearanceGenerator().generate(pb)
    widget_cos = pb.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)


def test_push_button_construct_appearances_is_no_op() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    pb.get_cos_object().set_item(_RECT, _rect(0, 0, 100, 30))

    pb.construct_appearances()

    widget_cos = pb.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None


# ---------- combo box ----------


def test_combo_box_generate_renders_value_text() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 20))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    cb.set_options(["alpha", "beta", "gamma"])

    cb.set_value("beta", regenerate_appearance=True)

    widget_cos = cb.get_widgets()[0].get_cos_object()
    ap = widget_cos.get_dictionary_object(_AP)
    assert isinstance(ap, COSDictionary)
    n = ap.get_dictionary_object(_N)
    assert isinstance(n, COSStream)
    body = n.create_input_stream().read()
    assert b"BT" in body
    assert b"ET" in body
    assert b"beta" in body
    assert b"/Tx BMC" in body
    assert b"EMC" in body


def test_combo_box_empty_value_no_text_string() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 20))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")

    cb.set_value(None, regenerate_appearance=True)

    widget_cos = cb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    # BT/ET still emitted, but no Tj because no value.
    assert b"BT" in body
    assert b"Tj" not in body


def test_combo_box_construct_appearances_creates_ap() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cos = cb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 20))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    cb.set_options(["alpha", "beta", "gamma"])
    cb.set_value("gamma")

    cb.construct_appearances()

    widget_cos = cb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"gamma" in body
    assert b"Tj" in body


# ---------- list box ----------


def test_list_box_generate_renders_single_value() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 60))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["one", "two", "three"])

    lb.set_value("two", regenerate_appearance=True)

    widget_cos = lb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"two" in body
    assert b"BT" in body
    assert b"Tj" in body


def test_list_box_generate_renders_multi_value_one_per_line() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 60))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_multi_select(True)

    lb.set_value(["one", "two"], regenerate_appearance=True)

    widget_cos = lb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"one" in body
    assert b"two" in body
    # One Tj per line.
    assert body.count(b"Tj") == 2
    # Subsequent lines use Td to drop the baseline.
    assert b"Td" in body


def test_list_box_set_value_no_regenerate_skips_ap() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 20))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_value("one")
    widget_cos = lb.get_widgets()[0].get_cos_object()
    assert widget_cos.get_dictionary_object(_AP) is None


def test_list_box_construct_appearances_creates_ap() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    cos = lb.get_cos_object()
    cos.set_item(_RECT, _rect(0, 0, 120, 60))
    cos.set_string(_DA, "/Helv 10 Tf 0 g")
    lb.set_options(["one", "two", "three"])
    lb.set_value("two")

    lb.construct_appearances()

    widget_cos = lb.get_widgets()[0].get_cos_object()
    n = widget_cos.get_dictionary_object(_AP).get_dictionary_object(_N)
    body = n.create_input_stream().read()
    assert b"two" in body
    assert b"Tj" in body
