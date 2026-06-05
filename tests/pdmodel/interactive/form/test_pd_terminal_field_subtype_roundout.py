"""Hand-written parity tests for the AcroForm terminal-field subtype
round-out (Wave 40).

These cover the upstream-exact accessor names that aren't exercised by
``test_pd_field_subclasses.py`` or ``test_pd_field_values.py`` — flag
aliases like ``do_not_spell_check``/``do_not_scroll``, the two-arg
``set_options`` overload, ``has_separate_export_and_display_values``,
radio-button selection accessors, signature ``set_default_value``, and
the multi-select gate on ``set_selected_options_indices``.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSStream
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox
from pypdfbox.pdmodel.interactive.form.pd_radio_button import PDRadioButton
from pypdfbox.pdmodel.interactive.form.pd_text_field import PDTextField

_AP: COSName = COSName.get_pdf_name("AP")
_N: COSName = COSName.get_pdf_name("N")
_AS: COSName = COSName.get_pdf_name("AS")
_OPT: COSName = COSName.get_pdf_name("Opt")
_KIDS: COSName = COSName.get_pdf_name("Kids")


# ---------- PDTextField ----------


def test_text_field_do_not_spell_check_alias_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.do_not_spell_check() is False
    tf.set_do_not_spell_check(True)
    assert tf.do_not_spell_check() is True
    assert tf.is_do_not_spell_check() is True


def test_text_field_do_not_scroll_alias_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    assert tf.do_not_scroll() is False
    tf.set_do_not_scroll(True)
    assert tf.do_not_scroll() is True
    assert tf.is_do_not_scroll() is True


def test_text_field_file_select_comb_rich_text_round_trip() -> None:
    form = PDAcroForm()
    tf = PDTextField(form)
    tf.set_file_select(True)
    tf.set_comb(True)
    tf.set_rich_text(True)
    assert tf.is_file_select() is True
    assert tf.is_comb() is True
    assert tf.is_rich_text() is True


# ---------- PDChoice options ----------


def test_choice_set_options_two_arg_writes_pairs() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_options(["e1", "e2"], ["Display 1", "Display 2"])
    assert cb.get_options_export_values() == ["e1", "e2"]
    assert cb.get_options_display_values() == ["Display 1", "Display 2"]
    assert cb.has_separate_export_and_display_values() is True

    raw = cb.get_cos_object().get_dictionary_object(_OPT)
    assert isinstance(raw, COSArray)
    first = raw.get_object(0)
    assert isinstance(first, COSArray)
    assert first.size() == 2


def test_choice_set_options_two_arg_size_mismatch_raises() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    with pytest.raises(ValueError):
        cb.set_options(["e1", "e2"], ["only one"])


def test_choice_set_options_two_arg_empty_clears_opt() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_options(["e1"], ["Display 1"])
    cb.set_options([], [])
    assert cb.get_cos_object().get_dictionary_object(_OPT) is None


def test_choice_set_options_two_arg_sort_pairs_by_display() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_sort(True)
    cb.set_options(["e_b", "e_a"], ["beta", "alpha"])
    # After sorting by display, pairs become (e_a, alpha), (e_b, beta).
    assert cb.get_options_export_values() == ["e_a", "e_b"]
    assert cb.get_options_display_values() == ["alpha", "beta"]


def test_choice_has_separate_export_and_display_values_false_when_flat() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_options(["a", "b", "c"])
    assert cb.has_separate_export_and_display_values() is False


def test_choice_set_selected_options_indices_clear_round_trip() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.get_selected_options_indices() == []
    lb.set_selected_options_indices([0, 2])
    assert lb.get_selected_options_indices() == [0, 2]
    lb.set_selected_options_indices(None)
    assert lb.get_selected_options_indices() == []


def test_choice_singular_alias_methods_match_plural() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_selected_options_index([1, 3])
    assert lb.get_selected_options_index() == [1, 3]
    assert lb.get_selected_options_indices() == [1, 3]


# ---------- PDRadioButton ----------


def _make_widget_with_on_state(on_value: str, *, is_on: bool) -> COSDictionary:
    """Helper: build a widget cos dict whose /AP /N has an on_value entry
    and whose /AS is either ``on_value`` (selected) or ``Off``."""
    widget = COSDictionary()
    ap = COSDictionary()
    n = COSDictionary()
    # Stream-valued states: on-value discovery filters to COSStream entries
    # via PDAppearanceEntry.get_sub_dictionary() (wave 1488).
    n.set_item(COSName.get_pdf_name(on_value), COSStream())
    n.set_item(COSName.get_pdf_name("Off"), COSStream())
    ap.set_item(_N, n)
    widget.set_item(_AP, ap)
    widget.set_item(_AS, COSName.get_pdf_name(on_value if is_on else "Off"))
    return widget


def test_radio_button_get_selected_index_all_off() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    kids = COSArray()
    kids.add(_make_widget_with_on_state("A", is_on=False))
    kids.add(_make_widget_with_on_state("B", is_on=False))
    rb.get_cos_object().set_item(_KIDS, kids)
    # All widgets have /AS = /Off → upstream returns -1.
    assert rb.get_selected_index() == -1


def test_radio_button_get_selected_index_walks_widgets() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    kids = COSArray()
    kids.add(_make_widget_with_on_state("Yes", is_on=False))
    kids.add(_make_widget_with_on_state("Choice2", is_on=True))
    kids.add(_make_widget_with_on_state("Choice3", is_on=False))
    rb.get_cos_object().set_item(_KIDS, kids)
    assert rb.get_selected_index() == 1


def test_radio_button_get_selected_export_values_no_opt_returns_value() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    # Write /V directly: upstream PDButton.setValue is strict and an AP-less
    # radio only knows on-value "" — but get_value()/getSelectedExportValues
    # read /V regardless of what setValue would have accepted.
    rb.get_cos_object().set_name(COSName.get_pdf_name("V"), "Choice2")
    # No /Opt -> selected export values is [getValue()].
    assert rb.get_selected_export_values() == ["Choice2"]


def test_radio_button_get_selected_export_values_with_opt() -> None:
    """Mirrors the export-value branch of upstream
    ``PDRadioButton.getSelectedExportValues``: when ``/Opt`` is non-empty,
    on_values comes from /Opt itself; the entries equal to ``getValue()``
    yield the matching export values.

    Wave 1372: ``set_value`` now dispatches into ``update_by_option`` when
    ``/Opt`` is present, which requires a 1:1 widget-to-option pairing.
    The read-side surface this test exercises does not need real widgets,
    so we write ``/V`` directly through the COS dictionary to bypass the
    new propagation path (matches the test's intent — the function under
    test is ``get_selected_export_values``).
    """
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["expA", "expB"])
    rb.get_cos_object().set_name(COSName.get_pdf_name("V"), "expB")
    selected = rb.get_selected_export_values()
    assert "expB" in selected


# ---------- PDButton.get_on_values ----------


def test_button_get_on_values_prefers_export_values() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    rb.set_export_values(["e1", "e2", "e1"])
    on_values = rb.get_on_values()
    assert on_values == {"e1", "e2"}


def test_button_get_on_values_walks_widgets_when_no_opt() -> None:
    form = PDAcroForm()
    rb = PDRadioButton(form)
    kids = COSArray()
    kids.add(_make_widget_with_on_state("Yes", is_on=False))
    kids.add(_make_widget_with_on_state("No", is_on=False))
    rb.get_cos_object().set_item(_KIDS, kids)
    on_values = rb.get_on_values()
    assert on_values == {"Yes", "No"}


# ---------- PDComboBox / PDListBox round-out ----------


def test_combo_box_set_value_then_clear_indices() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_options(["x", "y", "z"])
    cb.set_selected_options_indices([0, 2])
    assert cb.get_selected_options_indices() == [0, 2]
    cb.set_selected_options_indices(None)
    assert cb.get_selected_options_indices() == []


def test_list_box_top_index_round_trip() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.get_top_index() == 0
    lb.set_top_index(5)
    assert lb.get_top_index() == 5
    lb.set_top_index(None)
    assert lb.get_top_index() == 0
