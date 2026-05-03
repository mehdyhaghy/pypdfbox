from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName
from pypdfbox.pdmodel.interactive.action import (
    PDActionJavaScript,
    PDFormFieldAdditionalActions,
)
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_button import PDButton
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox
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


def test_text_field_has_max_len_predicate() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    # Fresh field — /MaxLen unset, predicate False, getter returns -1 sentinel.
    assert tf.has_max_len() is False
    assert tf.get_max_len() == -1

    tf.set_max_len(0)
    # 0 is a valid set value distinct from "unset".
    assert tf.has_max_len() is True
    assert tf.get_max_len() == 0

    # Even an explicit -1 is a "set" value.
    tf.set_max_len(-1)
    assert tf.has_max_len() is True


def test_text_field_has_value_and_has_default_value_predicates() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.has_value() is False
    assert tf.has_default_value() is False

    tf.set_value("v")
    tf.set_default_value("dv")
    assert tf.has_value() is True
    assert tf.has_default_value() is True

    tf.set_value(None)
    tf.set_default_value(None)
    assert tf.has_value() is False
    assert tf.has_default_value() is False


def test_text_field_has_value_does_not_walk_inheritance() -> None:
    """has_value is a local-dictionary check — even when /V is inherited from
    a parent, has_value must return False if the child's own dict has no /V."""
    from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
        PDNonTerminalField,
    )

    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.get_cos_object().set_string(COSName.get_pdf_name("V"), "from-parent")
    parent.get_cos_object().set_string(COSName.get_pdf_name("DV"), "from-parent-dv")

    child = PDTextField(form, COSDictionary(), parent=parent)
    # Effective value walks the chain...
    assert child.get_value() == "from-parent"
    assert child.get_default_value() == "from-parent-dv"
    # ...but the predicate only inspects the local dictionary.
    assert child.has_value() is False
    assert child.has_default_value() is False


def test_text_field_set_default_value_clears_with_none() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_default_value("x")
    assert tf.get_default_value() == "x"
    tf.set_default_value(None)
    assert tf.get_default_value() == ""
    assert (
        tf.get_cos_object().get_dictionary_object(COSName.get_pdf_name("DV")) is None
    )


def test_text_field_remaining_flags_round_trip_independently() -> None:
    """FILE_SELECT / DO_NOT_SPELL_CHECK / DO_NOT_SCROLL / COMB / RICH_TEXT
    map to bits 21/23/24/25/26 — verify each flips independently and the
    bitmask matches the upstream constant."""
    form = PDAcroForm()
    tf = PDTextField(form)

    # All defaults are False on a fresh field.
    assert tf.is_file_select() is False
    assert tf.is_do_not_spell_check() is False
    assert tf.is_do_not_scroll() is False
    assert tf.is_comb() is False
    assert tf.is_rich_text() is False

    tf.set_file_select(True)
    tf.set_do_not_spell_check(True)
    tf.set_do_not_scroll(True)
    tf.set_comb(True)
    tf.set_rich_text(True)

    assert tf.is_file_select() is True
    assert tf.is_do_not_spell_check() is True
    assert tf.is_do_not_scroll() is True
    assert tf.is_comb() is True
    assert tf.is_rich_text() is True

    # All five bits set, plus none of the bottom three (read_only/required/no_export).
    expected = (
        PDTextField.FLAG_FILE_SELECT
        | PDTextField.FLAG_DO_NOT_SPELL_CHECK
        | PDTextField.FLAG_DO_NOT_SCROLL
        | PDTextField.FLAG_COMB
        | PDTextField.FLAG_RICH_TEXT
    )
    assert tf.get_field_flags() == expected
    assert tf.is_read_only() is False

    # Clear one — verify the rest are unaffected.
    tf.set_comb(False)
    assert tf.is_comb() is False
    assert tf.is_file_select() is True
    assert tf.is_do_not_spell_check() is True
    assert tf.is_do_not_scroll() is True
    assert tf.is_rich_text() is True


def test_text_field_do_not_spell_check_alias_matches_predicate() -> None:
    """``do_not_spell_check`` is the upstream Java spelling; verify it
    returns the same value as ``is_do_not_spell_check``."""
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.do_not_spell_check() == tf.is_do_not_spell_check()

    tf.set_do_not_spell_check(True)
    assert tf.do_not_spell_check() is True
    assert tf.do_not_spell_check() == tf.is_do_not_spell_check()


def test_text_field_do_not_scroll_alias_matches_predicate() -> None:
    """``do_not_scroll`` mirrors the upstream Java name."""
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.do_not_scroll() == tf.is_do_not_scroll()

    tf.set_do_not_scroll(True)
    assert tf.do_not_scroll() is True
    assert tf.do_not_scroll() == tf.is_do_not_scroll()


def test_text_field_flag_constants_match_pdf_spec() -> None:
    """Concrete bit-values per PDF 32000-1 §12.7.4.3, Table 228 — guard
    against accidental bit drift on the FLAG_* constants."""
    assert PDTextField.FLAG_MULTILINE == 1 << 12
    assert PDTextField.FLAG_PASSWORD == 1 << 13
    assert PDTextField.FLAG_FILE_SELECT == 1 << 20
    assert PDTextField.FLAG_DO_NOT_SPELL_CHECK == 1 << 22
    assert PDTextField.FLAG_DO_NOT_SCROLL == 1 << 23
    assert PDTextField.FLAG_COMB == 1 << 24
    assert PDTextField.FLAG_RICH_TEXT == 1 << 25


def test_text_field_remove_max_len_clears_entry() -> None:
    """``remove_max_len`` removes ``/MaxLen`` from the field's own dict;
    ``has_max_len`` returns ``False`` and ``get_max_len`` returns the
    sentinel ``-1`` afterwards."""
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_max_len(120)
    assert tf.has_max_len() is True
    assert tf.get_max_len() == 120

    tf.remove_max_len()
    assert tf.has_max_len() is False
    assert tf.get_max_len() == -1
    # The /MaxLen key is gone from the underlying dictionary.
    assert (
        tf.get_cos_object().get_dictionary_object(COSName.get_pdf_name("MaxLen"))
        is None
    )


def test_text_field_remove_max_len_is_no_op_when_absent() -> None:
    """``remove_max_len`` is a no-op when the entry isn't present —
    callers can call it unconditionally on flush."""
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.has_max_len() is False
    # Must not raise.
    tf.remove_max_len()
    assert tf.has_max_len() is False
    assert tf.get_max_len() == -1


def test_text_field_get_value_decodes_cos_stream_payload() -> None:
    """``/V`` admits a COSStream payload per PDF 32000-1 §12.7.4.3 (text
    string OR text stream). ``get_value`` mirrors upstream
    ``getStringOrStream`` and decodes via ``COSStream.toTextString``."""
    from pypdfbox.cos import COSStream

    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(COSName.get_pdf_name("FT"), "Tx")

    v_stream = COSStream()
    with v_stream.create_output_stream() as sink:
        sink.write(b"streamed-value")
    field.set_item(COSName.get_pdf_name("V"), v_stream)

    tf = PDTextField(form, field)
    assert tf.get_value() == "streamed-value"
    # The local predicate sees the entry regardless of underlying COS type.
    assert tf.has_value() is True


def test_text_field_get_default_value_decodes_cos_stream_payload() -> None:
    """``/DV`` likewise admits a stream payload — verify the same decode
    path."""
    from pypdfbox.cos import COSStream

    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(COSName.get_pdf_name("FT"), "Tx")

    dv_stream = COSStream()
    with dv_stream.create_output_stream() as sink:
        sink.write(b"streamed-default")
    field.set_item(COSName.get_pdf_name("DV"), dv_stream)

    tf = PDTextField(form, field)
    assert tf.get_default_value() == "streamed-default"
    assert tf.has_default_value() is True


def test_text_field_get_value_returns_empty_string_for_unsupported_type() -> None:
    """When ``/V`` is some other COS type (e.g. a ``COSArray``) the upstream
    ``getStringOrStream`` falls through to ``""``. We must NOT return
    ``None`` from the public ``get_value`` even though the inner helper
    can — non-null contract."""
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(COSName.get_pdf_name("FT"), "Tx")
    field.set_item(COSName.get_pdf_name("V"), COSArray())

    tf = PDTextField(form, field)
    assert tf.get_value() == ""
    assert isinstance(tf.get_value(), str)


def test_text_field_get_default_value_returns_empty_string_for_unsupported_type() -> None:
    """Mirror of the ``get_value`` non-null guarantee for ``/DV``."""
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(COSName.get_pdf_name("FT"), "Tx")
    field.set_item(COSName.get_pdf_name("DV"), COSArray())

    tf = PDTextField(form, field)
    assert tf.get_default_value() == ""
    assert isinstance(tf.get_default_value(), str)


def test_text_field_get_value_walks_inheritance_with_stream_payload() -> None:
    """``/V`` is inheritable; verify the COSStream branch is reached even
    when the value lives on a parent field."""
    from pypdfbox.cos import COSStream
    from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
        PDNonTerminalField,
    )

    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    v_stream = COSStream()
    with v_stream.create_output_stream() as sink:
        sink.write(b"inherited-stream")
    parent.get_cos_object().set_item(COSName.get_pdf_name("V"), v_stream)

    child = PDTextField(form, COSDictionary(), parent=parent)
    assert child.get_value() == "inherited-stream"
    # Local predicate stays False — the entry lives on the parent.
    assert child.has_value() is False


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


def test_radio_button_no_toggle_to_off_round_trip() -> None:
    """``NoToggleToOff`` is /Ff bit 14 — upstream declares but does not
    expose the accessor. Verify the predicate / setter round-trip and do
    not collide with the in-unison bit (25) or the radio bit (15)."""
    form = PDAcroForm()
    rb = PDRadioButton(form)
    assert rb.is_no_toggle_to_off() is False
    rb.set_no_toggle_to_off(True)
    assert rb.is_no_toggle_to_off() is True

    # Adjacent bits are unaffected.
    assert rb.is_radio_button() is True
    assert rb.is_radios_in_unison() is False

    rb.set_no_toggle_to_off(False)
    assert rb.is_no_toggle_to_off() is False
    assert rb.is_radio_button() is True


def test_radio_button_no_toggle_to_off_independent_of_radios_in_unison() -> None:
    """Bit 14 (NoToggleToOff) and bit 25 (RadiosInUnison) are independent."""
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_radios_in_unison(True)
    rb.set_no_toggle_to_off(True)
    assert rb.is_radios_in_unison() is True
    assert rb.is_no_toggle_to_off() is True

    rb.set_radios_in_unison(False)
    assert rb.is_no_toggle_to_off() is True
    assert rb.is_radios_in_unison() is False


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
    lb.set_multi_select(True)
    lb.set_value(["one", "two"])
    assert lb.get_value() == ["one", "two"]


def test_choice_selected_indices_round_trip() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.get_selected_options_indices() == []
    # Upstream PDFBox: setSelectedOptionsIndex requires the MULTI_SELECT flag.
    lb.set_multi_select(True)
    lb.set_selected_options_indices([0, 2, 5])
    assert lb.get_selected_options_indices() == [0, 2, 5]


# ---------- PDSignatureField ----------


def test_signature_field_fresh_has_ft_sig() -> None:
    form = PDAcroForm()
    sig = PDSignatureField(form)
    assert sig.get_field_type() == "Sig"
    assert sig.get_cos_object().get_name(COSName.get_pdf_name("FT")) == "Sig"
    assert sig.get_partial_name() == "Signature1"
    assert sig.get_signature() is None
    widget = sig.get_widgets()[0]
    assert widget.get_subtype() == "Widget"
    assert widget.is_printed() is True
    assert widget.is_locked() is True


def test_signature_field_fresh_name_skips_existing_signature_fields() -> None:
    form = PDAcroForm()
    first = PDSignatureField(form)
    form.set_fields([first])

    second = PDSignatureField(form)

    assert first.get_partial_name() == "Signature1"
    assert second.get_partial_name() == "Signature2"


def test_signature_field_raw_value_round_trip() -> None:
    from pypdfbox.pdmodel.interactive.digitalsignature import PDSeedValue, PDSignature

    form = PDAcroForm()
    sig = PDSignatureField(form)
    raw = COSDictionary()
    raw.set_string(COSName.get_pdf_name("Type"), "Sig")
    sig.set_value(raw)
    resolved_sig = sig.get_signature()
    assert isinstance(resolved_sig, PDSignature)
    assert resolved_sig.get_cos_object() is raw
    assert sig.get_value().get_cos_object() is raw

    seed = COSDictionary()
    sig.set_seed_value(seed)
    resolved_seed = sig.get_seed_value()
    assert isinstance(resolved_seed, PDSeedValue)
    assert resolved_seed.get_cos_object() is seed

    from pypdfbox.pdmodel.interactive.digitalsignature import PDSignatureLock

    lock = COSDictionary()
    sig.set_lock(lock)
    resolved_lock = sig.get_lock()
    assert isinstance(resolved_lock, PDSignatureLock)
    assert resolved_lock.get_cos_object() is lock


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


def test_variable_text_default_appearance_updates_existing_widget_kid_da() -> None:
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(COSName.get_pdf_name("FT"), "Tx")

    first_widget = COSDictionary()
    first_widget.set_string(COSName.get_pdf_name("DA"), "/Helv 9 Tf 0 g")
    second_widget = COSDictionary()
    field.set_item(COSName.get_pdf_name("Kids"), COSArray([first_widget, second_widget]))

    tf = PDTextField(form, field)
    tf.set_default_appearance("/F1 12 Tf 0 g")

    assert tf.get_default_appearance() == "/F1 12 Tf 0 g"
    assert first_widget.get_string(COSName.get_pdf_name("DA")) == "/F1 12 Tf 0 g"
    assert not second_widget.contains_key(COSName.get_pdf_name("DA"))


def test_variable_text_default_appearance_none_removes_existing_widget_kid_da() -> None:
    form = PDAcroForm()
    field = COSDictionary()
    field.set_name(COSName.get_pdf_name("FT"), "Tx")
    field.set_string(COSName.get_pdf_name("DA"), "/Helv 9 Tf 0 g")
    widget = COSDictionary()
    widget.set_string(COSName.get_pdf_name("DA"), "/Helv 9 Tf 0 g")
    field.set_item(COSName.get_pdf_name("Kids"), COSArray([widget]))

    tf = PDTextField(form, field)
    tf.set_default_appearance(None)

    assert tf.get_default_appearance() is None
    assert not widget.contains_key(COSName.get_pdf_name("DA"))


def test_terminal_field_additional_actions_round_trip_typed_actions() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    actions = PDFormFieldAdditionalActions()
    javascript = PDActionJavaScript()
    javascript.set_action("event.value = event.value.toUpperCase();")

    actions.set_k(javascript)
    tf.set_actions(actions)

    assert tf.get_cos_object().get_dictionary_object(COSName.get_pdf_name("AA")) is (
        actions.get_cos_object()
    )
    resolved_actions = tf.get_actions()
    assert isinstance(resolved_actions, PDFormFieldAdditionalActions)
    resolved_action = resolved_actions.get_k()
    assert isinstance(resolved_action, PDActionJavaScript)
    assert resolved_action.get_action() == "event.value = event.value.toUpperCase();"

    tf.set_actions(None)
    assert tf.get_actions() is None
    assert not tf.get_cos_object().contains_key(COSName.get_pdf_name("AA"))


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


def test_button_get_export_values_accepts_single_cos_string() -> None:
    """Upstream ``PDButton.getExportValues`` returns a one-element list when
    ``/Opt`` is a lone ``COSString`` (not wrapped in a ``COSArray``)."""
    from pypdfbox.cos import COSString

    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.get_cos_object().set_item(COSName.get_pdf_name("Opt"), COSString("solo"))
    assert rb.get_export_values() == ["solo"]


def test_button_get_export_values_inherits_from_parent() -> None:
    """``getExportValues`` walks the inheritable chain — a child with no /Opt
    surfaces the parent's ``/Opt`` array."""
    from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
        PDNonTerminalField,
    )

    form = PDAcroForm()
    parent = PDNonTerminalField(form)
    parent.get_cos_object().set_item(
        COSName.get_pdf_name("Opt"), COSArray.of_cos_strings(["a", "b"])
    )
    child = PDRadioButton(form, COSDictionary(), parent=parent)
    assert child.get_export_values() == ["a", "b"]


def test_button_set_value_by_index_writes_string_index() -> None:
    """``setValue(int)`` writes the index as a ``/V`` name; ``get_value``
    decodes the integer-string back through the export values."""
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["alpha", "beta", "gamma"])

    rb.set_value_by_index(1)

    assert rb.get_cos_object().get_name(COSName.get_pdf_name("V")) == "1"
    # get_value decodes the numeric /V back through /Opt.
    assert rb.get_value() == "beta"


def test_button_set_value_by_index_rejects_out_of_range() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["alpha", "beta"])
    with pytest.raises(ValueError, match="not a valid index"):
        rb.set_value_by_index(5)
    with pytest.raises(ValueError, match="not a valid index"):
        rb.set_value_by_index(-1)


def test_button_set_value_by_index_rejects_when_no_export_values() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    with pytest.raises(ValueError, match="not a valid index"):
        rb.set_value_by_index(0)


def test_button_check_value_accepts_off() -> None:
    """``checkValue`` always allows ``"Off"``."""
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["yes", "no"])
    # No raise:
    rb.check_value("Off")
    rb.check_value("yes")
    rb.check_value("no")


def test_button_check_value_rejects_unknown() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["yes", "no"])
    with pytest.raises(ValueError, match="not a valid option"):
        rb.check_value("maybe")


def test_button_get_value_decodes_numeric_v_via_export_values() -> None:
    """When ``/V`` parses as an integer in range, return the export value."""
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["alpha", "beta", "gamma"])
    rb.get_cos_object().set_name(COSName.get_pdf_name("V"), "2")
    assert rb.get_value() == "gamma"


def test_button_get_value_returns_raw_v_when_index_out_of_range() -> None:
    """If ``/V`` is numeric but outside the export-values range, the raw name
    is returned (mirrors upstream's fall-through)."""
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["alpha"])
    rb.get_cos_object().set_name(COSName.get_pdf_name("V"), "9")
    assert rb.get_value() == "9"


def test_button_get_value_default_is_off_when_unset() -> None:
    """Per PDF spec, an unset ``/V`` on a button reports ``"Off"``."""
    form = PDAcroForm()
    rb = PDRadioButton(form)
    # Fresh radio button has no /V.
    assert rb.get_value() == "Off"
