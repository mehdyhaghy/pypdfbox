from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
    PDNonTerminalField,
)
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_V: COSName = COSName.get_pdf_name("V")
_FT: COSName = COSName.get_pdf_name("FT")


# ---------- Text field ----------


def test_text_field_value_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_value("hello")
    assert tf.get_value() == "hello"
    assert tf.get_value_as_string() == "hello"
    # /V is stored as COSString per PDF 32000-1 §12.7.4.3
    raw = tf.get_cos_object().get_dictionary_object(_V)
    assert isinstance(raw, COSString)
    assert raw.get_string() == "hello"


def test_text_field_clear_value() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_value("x")
    tf.set_value(None)
    assert tf.get_value() == ""
    assert tf.get_cos_object().get_dictionary_object(_V) is None


def test_text_field_inherits_value_from_parent() -> None:
    """Per PDF 32000-1 §12.7.4: a field with no /V inherits from /Parent."""
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.get_cos_object().set_string(_V, "abc")

    child = PDTextField(form, COSDictionary(), parent=parent)
    # child has no /V
    assert child.get_cos_object().get_dictionary_object(_V) is None
    # ...but inherits "abc" from parent
    assert child.get_value() == "abc"
    assert child.get_value_as_string() == "abc"


def test_text_field_own_value_shadows_parent() -> None:
    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.get_cos_object().set_string(_V, "from-parent")

    child = PDTextField(form, COSDictionary(), parent=parent)
    child.set_value("from-child")
    assert child.get_value() == "from-child"


# ---------- Check box ----------


def test_check_box_set_value_writes_cos_name() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.set_value("Yes")
    assert cb.get_value() == "Yes"
    assert cb.get_value_as_string() == "Yes"
    raw = cb.get_cos_object().get_dictionary_object(_V)
    assert isinstance(raw, COSName)
    assert raw.name == "Yes"


def test_check_box_off_value() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    cb.set_value("Off")
    assert cb.get_value() == "Off"
    raw = cb.get_cos_object().get_dictionary_object(_V)
    assert isinstance(raw, COSName)


# ---------- Radio button ----------


def test_radio_button_value_round_trip() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_value("Choice2")
    assert rb.get_value() == "Choice2"
    assert rb.get_value_as_string() == "Choice2"
    raw = rb.get_cos_object().get_dictionary_object(_V)
    assert isinstance(raw, COSName)
    assert raw.name == "Choice2"


# ---------- Push button ----------


def test_push_button_value_is_empty_and_does_not_raise() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    # Per upstream PDFBox: push button has no value, returns "".
    assert pb.get_value() == ""
    assert pb.get_value_as_string() == ""
    # set_value flows through the inherited PDButton path without raising.
    pb.set_value("ignored")  # no-op semantically per upstream
    # get_value still returns "" (PDPushButton overrides the read side).
    assert pb.get_value() == ""


# ---------- Choice (combo + list) ----------


def test_combo_box_single_value_round_trip() -> None:
    form = PDAcroForm()
    combo = PDComboBox(form)
    combo.set_value("Apple")
    assert combo.get_value() == ["Apple"]
    assert combo.get_value_as_string() == "Apple"


def test_list_box_multi_value_round_trip() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_value(["A", "B"])
    assert lb.get_value() == ["A", "B"]
    assert lb.get_value_as_string() == "A,B"
    raw = lb.get_cos_object().get_dictionary_object(_V)
    assert isinstance(raw, COSArray)
    assert raw.size() == 2


def test_choice_clear_value() -> None:
    form = PDAcroForm()
    combo = PDComboBox(form)
    combo.set_value(["x", "y"])
    combo.set_value(None)
    assert combo.get_value() == []
    assert combo.get_value_as_string() == ""


# ---------- Signature field ----------


def test_signature_field_value_as_string_is_empty() -> None:
    form = PDAcroForm()
    sig = PDSignatureField(form)
    assert sig.get_value() is None
    assert sig.get_value_as_string() == ""


def test_signature_field_set_raw_value_round_trip() -> None:
    form = PDAcroForm()
    sig = PDSignatureField(form)
    raw = COSDictionary()
    raw.set_name(COSName.get_pdf_name("Type"), "Sig")
    sig.set_value(raw)
    resolved = sig.get_value()
    assert resolved is not None
    assert resolved.get_cos_object() is raw
    # get_value_as_string still returns "" — signatures are not single-string.
    assert sig.get_value_as_string() == ""


# ---------- Non-terminal field ----------


def test_non_terminal_field_get_value_returns_own_v() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    assert nt.get_value() is None
    nt.set_value(COSString("group-value"))
    item = nt.get_value()
    assert isinstance(item, COSString)
    assert item.get_string() == "group-value"
    assert nt.get_value_as_string() == "group-value"


def test_non_terminal_field_value_as_string_for_name() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.set_value(COSName.get_pdf_name("On"))
    assert nt.get_value_as_string() == "On"


def test_non_terminal_field_clear_value() -> None:
    form = PDAcroForm()
    nt = PDNonTerminalField(form)
    nt.set_value(COSString("x"))
    nt.set_value(None)
    assert nt.get_value() is None
    assert nt.get_value_as_string() == ""
