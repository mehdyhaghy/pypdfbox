from __future__ import annotations

import pytest

from pypdfbox.cos import COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_push_button import PDPushButton
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.interactive.form.pd_signature_field import PDSignatureField
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField
from pypdfbox.pdmodel.interactive.form.pd_variable_text import PDVariableText


# ---------- PDTextField ----------


def test_text_field_fresh_has_ft_tx() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_field_type() == "Tx"
    assert tf.get_cos_object().get_name(COSName.get_pdf_name("FT")) == "Tx"


def test_text_field_multiline_and_password_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.is_multiline() is False
    assert tf.is_password() is False

    tf.set_multiline(True)
    tf.set_password(True)
    assert tf.is_multiline() is True
    assert tf.is_password() is True
    flags = tf.get_field_flags()
    assert flags & PDTextField.FLAG_MULTILINE
    assert flags & PDTextField.FLAG_PASSWORD

    tf.set_multiline(False)
    assert tf.is_multiline() is False
    assert tf.is_password() is True


def test_text_field_max_len_and_value_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_max_len() == -1
    assert tf.get_value() == ""

    tf.set_max_len(42)
    tf.set_value("hello")
    assert tf.get_max_len() == 42
    assert tf.get_value() == "hello"
    assert tf.get_value_as_string() == "hello"

    tf.set_default_value("default")
    assert tf.get_default_value() == "default"


# ---------- PDPushButton / PDRadioButton / PDCheckBox ----------


def test_push_button_fresh_is_push_button() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    assert pb.get_field_type() == "Btn"
    assert pb.is_push_button() is True
    assert pb.is_radio_button() is False
    # Push buttons report empty value/export per upstream
    assert pb.get_value() == ""
    assert pb.get_export_values() == []


def test_push_button_set_export_values_rejects_non_empty() -> None:
    form = PDAcroForm()
    pb = PDPushButton(form)
    with pytest.raises(ValueError):
        pb.set_export_values(["a"])
    # Empty is allowed
    pb.set_export_values([])
    pb.set_export_values(None)


def test_radio_button_fresh_is_radio_button() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    assert rb.get_field_type() == "Btn"
    assert rb.is_radio_button() is True
    assert rb.is_push_button() is False
    assert rb.is_radios_in_unison() is False
    rb.set_radios_in_unison(True)
    assert rb.is_radios_in_unison() is True


def test_check_box_check_un_check_toggles_value() -> None:
    form = PDAcroForm()
    cb = PDCheckBox(form)
    assert cb.get_field_type() == "Btn"
    assert cb.is_push_button() is False
    assert cb.is_radio_button() is False

    assert cb.is_checked() is False
    cb.check()
    assert cb.get_value() != ""
    assert cb.get_value() != "Off"
    assert cb.is_checked() is True

    cb.un_check()
    assert cb.get_value() == "Off"
    assert cb.is_checked() is False


# ---------- PDComboBox / PDListBox ----------


def test_combo_box_fresh_is_combo_with_options_round_trip() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    assert cb.get_field_type() == "Ch"
    assert cb.is_combo() is True

    assert cb.get_options() == []
    cb.set_options(["a", "b"])
    assert cb.get_options() == ["a", "b"]
    assert cb.get_options_export_values() == ["a", "b"]
    assert cb.get_options_display_values() == ["a", "b"]


def test_combo_box_edit_flag_round_trip() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    assert cb.is_edit() is False
    cb.set_edit(True)
    assert cb.is_edit() is True


def test_list_box_fresh_is_not_combo() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.get_field_type() == "Ch"
    assert lb.is_combo() is False


def test_choice_value_single_and_multi_round_trip() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.get_value() == []
    lb.set_value("one")
    assert lb.get_value() == ["one"]
    lb.set_value(["one", "two"])
    assert lb.get_value() == ["one", "two"]


def test_choice_selected_indices_round_trip() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.get_selected_options_indices() == []
    lb.set_selected_options_indices([0, 2, 5])
    assert lb.get_selected_options_indices() == [0, 2, 5]


# ---------- PDSignatureField ----------


def test_signature_field_fresh_has_ft_sig() -> None:
    form = PDAcroForm()
    sig = PDSignatureField(form)
    assert sig.get_field_type() == "Sig"
    assert sig.get_cos_object().get_name(COSName.get_pdf_name("FT")) == "Sig"
    assert sig.get_signature() is None


def test_signature_field_raw_value_round_trip() -> None:
    form = PDAcroForm()
    sig = PDSignatureField(form)
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("Type"), "Sig")
    sig.set_value(raw)
    assert sig.get_signature() is raw
    assert sig.get_value() is raw

    seed = COSDictionary()
    sig.set_seed_value(seed)
    assert sig.get_seed_value() is seed

    lock = COSDictionary()
    sig.set_lock(lock)
    assert sig.get_lock() is lock


# ---------- PDVariableText ----------


def test_variable_text_default_appearance_and_q_round_trip_on_text_field() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.get_default_appearance() is None
    assert tf.get_q() == 0

    tf.set_default_appearance("/Helv 12 Tf 0 g")
    tf.set_q(PDVariableText.QUADDING_CENTERED)
    assert tf.get_default_appearance() == "/Helv 12 Tf 0 g"
    assert tf.get_q() == PDVariableText.QUADDING_CENTERED

    tf.set_default_style_string("font: Helvetica")
    tf.set_rich_text_value("<body>Hi</body>")
    assert tf.get_default_style_string() == "font: Helvetica"
    assert tf.get_rich_text_value() == "<body>Hi</body>"


# ---------- PDButton common surface ----------


def test_button_export_values_round_trip() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    assert rb.get_export_values() == []
    rb.set_export_values(["yes", "no", "maybe"])
    assert rb.get_export_values() == ["yes", "no", "maybe"]
    rb.set_export_values(None)
    assert rb.get_export_values() == []


def test_button_set_push_clears_radio_and_vice_versa() -> None:
    form = PDAcroForm()
    btn = PDButton(form)
    btn.set_push_button(True)
    assert btn.is_push_button() is True
    assert btn.is_radio_button() is False
    btn.set_radio_button(True)
    assert btn.is_radio_button() is True
    assert btn.is_push_button() is False
