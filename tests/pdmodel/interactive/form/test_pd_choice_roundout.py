"""PDChoice round-out — set_value edge cases and option/index round-trips.

Hand-written tests covering remaining gaps on the choice base class:
``set_value([])`` clears /V and /I (mirrors upstream's empty-list branch),
the value/options inheritance walk, /TI getter default, and assorted flag
predicates.
"""
from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSDictionary, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.interactive.form.pd_list_box import PDListBox

_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_I: COSName = COSName.get_pdf_name("I")
_OPT: COSName = COSName.get_pdf_name("Opt")
_TI: COSName = COSName.get_pdf_name("TI")


# ---------- set_value([]) — empty-list branch ----------


def test_set_value_empty_list_clears_v_and_i() -> None:
    """Mirrors upstream ``PDChoice.setValue(List)`` empty-list branch which
    removes ``/V`` and ``/I`` rather than writing an empty COSArray.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["a", "b", "c"])
    lb.set_multi_select(True)
    lb.set_value(["a", "c"])

    cos = lb.get_cos_object()
    assert cos.contains_key(_V)
    assert cos.contains_key(_I)

    lb.set_value([])

    assert not cos.contains_key(_V)
    assert not cos.contains_key(_I)
    assert lb.get_value() == []
    assert lb.get_selected_options_indices() == []


def test_set_value_none_clears_v_and_i() -> None:
    """``set_value(None)`` is symmetric with the empty-list branch."""
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["a", "b"])
    lb.set_multi_select(True)
    lb.set_value(["a"])

    cos = lb.get_cos_object()
    assert cos.contains_key(_V)

    lb.set_value(None)
    assert not cos.contains_key(_V)
    assert not cos.contains_key(_I)


# ---------- _selected_option_indices_for_values via set_value ----------


def test_set_value_string_writes_cos_string_and_clears_indices() -> None:
    """A single-string ``set_value`` writes a COSString and *removes*
    any existing ``/I`` entry. Mirrors upstream
    ``PDChoice.setValue(String)`` which terminates with
    ``setSelectedOptionsIndex(null)`` (wave 1372 closed the divergence
    that previously had pypdfbox writing both ``/V`` and ``/I`` on the
    single-value path)."""
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["alpha", "beta", "gamma"])

    # Pre-populate /I so we can prove set_value(str) clears it.
    lb.set_selected_options_indices([0])

    lb.set_value("beta")
    assert lb.get_value() == ["beta"]
    # /I must be absent — upstream contract.
    assert lb.get_selected_options_indices() == []
    assert not lb.get_cos_object().contains_key(_I)
    v = lb.get_cos_object().get_dictionary_object(_V)
    assert isinstance(v, COSString)


def test_set_value_list_rejects_value_not_in_options() -> None:
    """The list overload validates membership in ``/Opt`` (mirrors upstream
    ``PDChoice.setValue(List)`` ``containsAll`` check)."""
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["a", "b"])
    lb.set_multi_select(True)

    with pytest.raises(ValueError):
        lb.set_value(["a", "missing"])


def test_set_value_multi_value_requires_multi_select() -> None:
    """A list with more than one entry on a non-multi-select choice raises."""
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["a", "b"])

    with pytest.raises(ValueError):
        lb.set_value(["a", "b"])


def test_set_value_combo_box_with_edit_skips_validation() -> None:
    """Combo + edit lets free-text values bypass the option-membership check
    (mirrors the editable combo-box behavior)."""
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_options(["a", "b"])
    cb.set_edit(True)

    cb.set_value("free-text")
    assert cb.get_value() == ["free-text"]
    # No /I gets written when the value is not in /Opt.
    assert cb.get_selected_options_indices() == []


# ---------- /I round-trip ----------


def test_get_selected_options_indices_ignores_non_integer_entries() -> None:
    """Defensive: malformed ``/I`` entries (non-integers) are silently
    skipped — mirrors upstream's ``toCOSNumberIntegerList`` filtering.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    arr = COSArray()
    arr.add(COSInteger(0))
    arr.add(COSString("garbage"))
    arr.add(COSInteger(2))
    lb.get_cos_object().set_item(_I, arr)

    assert lb.get_selected_options_indices() == [0, 2]


def test_set_selected_options_indices_none_and_empty_remove_i() -> None:
    """Both ``None`` and ``[]`` clear ``/I`` (port intentional permissive form
    — does not enforce the multi-select flag, see CHANGES.md wave 40)."""
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_multi_select(True)
    lb.set_selected_options_indices([0, 1])
    assert lb.get_cos_object().contains_key(_I)

    lb.set_selected_options_indices(None)
    assert not lb.get_cos_object().contains_key(_I)

    lb.set_selected_options_indices([0])
    assert lb.get_cos_object().contains_key(_I)
    lb.set_selected_options_indices([])
    assert not lb.get_cos_object().contains_key(_I)


# ---------- /Opt removal via set_options(None / []) ----------


def test_set_options_none_removes_opt() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["x", "y"])
    assert lb.get_cos_object().contains_key(_OPT)

    lb.set_options(None)
    assert not lb.get_cos_object().contains_key(_OPT)


def test_set_options_empty_list_removes_opt() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["x", "y"])
    lb.set_options([])
    assert not lb.get_cos_object().contains_key(_OPT)


def test_set_options_two_arg_partial_empty_clears_opt() -> None:
    """Either side empty in the two-arg overload removes /Opt (matches
    upstream branch where any empty list short-circuits to removal).
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["a", "b"], ["A", "B"])

    lb.set_options([], ["A", "B"])
    assert not lb.get_cos_object().contains_key(_OPT)

    lb.set_options(["a", "b"], ["A", "B"])
    lb.set_options(["a", "b"], [])
    assert not lb.get_cos_object().contains_key(_OPT)


# ---------- inheritable /V walk ----------


def test_get_value_walks_parent_chain_via_inheritable_attribute() -> None:
    """A choice's ``/V`` is an inheritable attribute — when the local field
    has none, the parent's ``/V`` shows through."""
    from pypdfbox.pdmodel.interactive.form.pd_non_terminal_field import (
        PDNonTerminalField,
    )

    form = PDAcroForm()
    parent_dict = COSDictionary()
    parent_dict.set_item(_V, COSString("inherited"))
    parent = PDNonTerminalField(form, parent_dict)

    leaf_dict = COSDictionary()
    leaf_dict.set_name(COSName.get_pdf_name("FT"), "Ch")
    lb = PDListBox(form, leaf_dict, parent)

    assert lb.get_value() == ["inherited"]


# ---------- /TI default ----------


def test_top_index_defaults_to_zero_when_absent() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    assert not lb.get_cos_object().contains_key(_TI)
    assert lb.get_top_index() == 0


def test_has_top_index_predicate_round_trip() -> None:
    """Pypdfbox-only ``has_top_index`` predicate distinguishes
    "explicit ``/TI = 0``" from "no ``/TI`` entry"."""
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.has_top_index() is False

    lb.set_top_index(0)
    assert lb.has_top_index() is True
    assert lb.get_top_index() == 0

    lb.set_top_index(7)
    assert lb.has_top_index() is True
    assert lb.get_top_index() == 7

    lb.set_top_index(None)
    assert lb.has_top_index() is False
    assert lb.get_top_index() == 0


# ---------- flag predicates ----------


def test_choice_flag_round_trips() -> None:
    """All choice flag setters/getters round-trip through /Ff."""
    form = PDAcroForm()
    lb = PDListBox(form)

    assert lb.is_sort() is False
    lb.set_sort(True)
    assert lb.is_sort() is True

    assert lb.is_multi_select() is False
    lb.set_multi_select(True)
    assert lb.is_multi_select() is True

    assert lb.is_do_not_spell_check() is False
    lb.set_do_not_spell_check(True)
    assert lb.is_do_not_spell_check() is True

    assert lb.is_commit_on_sel_change() is False
    lb.set_commit_on_sel_change(True)
    assert lb.is_commit_on_sel_change() is True

    # Clearing leaves the dict in a defined state.
    lb.set_sort(False)
    lb.set_multi_select(False)
    lb.set_do_not_spell_check(False)
    lb.set_commit_on_sel_change(False)
    assert lb.is_sort() is False
    assert lb.is_multi_select() is False
    assert lb.is_do_not_spell_check() is False
    assert lb.is_commit_on_sel_change() is False


# ---------- /DV inheritance + None removal ----------


def test_default_value_array_round_trip() -> None:
    """``/DV`` may be a COSArray of strings on multi-select fields."""
    form = PDAcroForm()
    lb = PDListBox(form)
    arr = COSArray()
    arr.add(COSString("x"))
    arr.add(COSString("y"))
    lb.get_cos_object().set_item(_DV, arr)
    assert lb.get_default_value() == ["x", "y"]


def test_set_default_value_none_removes_dv() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_default_value("seed")
    assert lb.get_cos_object().contains_key(_DV)

    lb.set_default_value(None)
    assert not lb.get_cos_object().contains_key(_DV)


# ---------- get_value_as_string ----------


def test_get_value_as_string_joins_multi_select() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["a", "b", "c"])
    lb.set_multi_select(True)
    lb.set_value(["a", "c"])
    # PDChoice.getValueAsString == Arrays.toString(getValue().toArray()).
    assert lb.get_value_as_string() == "[a, c]"


def test_get_value_as_string_empty_when_no_value() -> None:
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.get_value_as_string() == "[]"


# ---------- Wave 247: /Opt as COSString (FieldUtils.getPairableItems parity) ----------


def test_get_options_unwraps_cos_string_opt_singleton() -> None:
    """Mirrors upstream ``FieldUtils.getPairableItems`` — when /Opt is itself
    a ``COSString`` (out-of-spec but observed in the wild) the value is
    returned as a singleton list rather than dropped.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.get_cos_object().set_item(_OPT, COSString("only"))
    assert lb.get_options() == ["only"]
    assert lb.get_options_export_values() == ["only"]
    assert lb.get_options_display_values() == ["only"]


def test_get_options_display_values_unwraps_single_element_nested_options() -> None:
    """One-element nested /Opt entries are tolerated like export values.

    Upstream's choice-option parsing accepts this shape for ``getOptions``;
    display reads should not report a false export/display split when there
    is no second display element.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    first = COSArray()
    first.add(COSString("A"))
    second = COSArray()
    second.add(COSString("B"))
    lb.get_cos_object().set_item(_OPT, COSArray([first, second]))

    assert lb.get_options() == ["A", "B"]
    assert lb.get_options_display_values() == ["A", "B"]
    assert lb.has_separate_export_and_display_values() is False


def test_get_options_returns_empty_when_opt_is_unexpected_type() -> None:
    """A non-array, non-string /Opt yields an empty list — defensive parity
    with upstream's ``FieldUtils.getPairableItems`` final fall-through.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.get_cos_object().set_int(_OPT, 5)
    assert lb.get_options() == []
    assert lb.get_options_display_values() == []


# ---------- Wave 247: has_options predicate ----------


def test_has_options_predicate_round_trip() -> None:
    """Pypdfbox-only ``has_options`` distinguishes "no /Opt entry" from
    "explicit empty /Opt"."""
    form = PDAcroForm()
    lb = PDListBox(form)
    assert lb.has_options() is False

    lb.set_options(["a", "b"])
    assert lb.has_options() is True

    # set_options([]) removes /Opt — predicate flips back to False.
    lb.set_options([])
    assert lb.has_options() is False

    # An externally-written empty COSArray /Opt still registers.
    lb.get_cos_object().set_item(_OPT, COSArray())
    assert lb.has_options() is True
    assert lb.get_options() == []


# ---------- Wave 247: /I sorting on set_value (PDF 32000-1 §12.7.4.4) ----------


def test_set_value_sorts_selected_option_indices_ascending() -> None:
    """Per PDF 32000-1 §12.7.4.4, /I "shall be sorted in ascending order".
    Upstream ``PDChoice.updateSelectedOptionsIndex`` calls
    ``Collections.sort(indices)`` before writing /I — pypdfbox does the same.
    """
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["a", "b", "c", "d", "e"])
    lb.set_multi_select(True)

    lb.set_value(["d", "a", "c"])

    # /V preserves caller-supplied order (text strings).
    assert lb.get_value() == ["d", "a", "c"]
    # /I is sorted ascending regardless of /V order.
    assert lb.get_selected_options_indices() == [0, 2, 3]


def test_set_value_single_value_string_clears_indices() -> None:
    """Upstream ``PDChoice.setValue(String)`` clears ``/I`` after
    writing ``/V``. Wave 1372 closed the previous local divergence
    where the single-value path computed and wrote ``/I``."""
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_options(["a", "b", "c"])
    # Multi-value path (list) still records /I for the multi-select
    # contract; the single-value path drops it. Pre-seed via list.
    lb.set_multi_select(True)
    lb.set_value(["c"])
    assert lb.get_selected_options_indices() == [2]
    # Now the str overload clears /I.
    lb.set_multi_select(False)
    lb.set_value("c")
    assert lb.get_selected_options_indices() == []


# ---------- Wave 247: /TI ----------


def test_set_top_index_negative_value_round_trip() -> None:
    """Upstream ``setTopIndex`` performs no validation — negative values
    survive the round-trip."""
    form = PDAcroForm()
    lb = PDListBox(form)
    lb.set_top_index(-1)
    assert lb.get_top_index() == -1
    assert lb.has_top_index() is True


# ---------- Wave 1264: abstract construct_appearances ----------


def test_pd_choice_construct_appearances_is_abstract() -> None:
    """``PDChoice.construct_appearances`` mirrors upstream's
    ``abstract void constructAppearances()`` (PDChoice.java line 501).
    Calling it on a bare ``PDChoice`` (bypassing concrete subclasses)
    must raise ``NotImplementedError``.
    """
    from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice

    form = PDAcroForm()
    cb = PDComboBox(form)

    with pytest.raises(NotImplementedError):
        # Bypass the subclass override to reach the abstract base method.
        PDChoice.construct_appearances(cb)


def test_pd_choice_subclasses_override_construct_appearances() -> None:
    """``PDComboBox`` and ``PDListBox`` both provide concrete
    ``construct_appearances`` overrides, so the abstract base
    is never invoked through the normal MRO."""
    form = PDAcroForm()
    cb = PDComboBox(form)
    lb = PDListBox(form)

    # Should not raise — both subclasses dispatch into the appearance
    # generator, which is a no-op when there are no widgets.
    cb.construct_appearances()
    lb.construct_appearances()
