"""Hand-written parity tests for the ``PDComboBox`` round-out (Wave 183).

Targets small remaining gaps on the combo-box subclass surface:

- ``FLAG_EDIT`` class constant exposed directly on ``PDComboBox`` (upstream
  PDComboBox.java declares ``FLAG_EDIT`` privately on the class — re-exposing
  it here matches the upstream constant location even though PDChoice in
  this lite port carries the same value for dispatch convenience).
- Flag bits and ``/FT`` are preserved when ``PDComboBox`` is loaded from an
  existing dictionary (the ``new_field`` ctor branch only fires for fresh
  fields — callers reloading a saved combo box should get back exactly
  what's on disk).
- ``is_edit`` and ``is_combo`` reflect the ``/Ff`` bits read off the existing
  dictionary, not the synthesised ones.
- ``get_default_value`` round-trips through the inheritable ``/DV`` slot
  for both single-string and array shapes (upstream returns ``List<String>``
  uniformly).
- ``get_value_as_string`` collapses cleanly when ``/V`` is unset on a fresh
  combo box.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSDictionary, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox

_FT: COSName = COSName.get_pdf_name("FT")
_FF: COSName = COSName.get_pdf_name("Ff")
_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")


# ---------- FLAG_EDIT class constant ----------


def test_combo_box_flag_edit_class_constant_matches_upstream_value() -> None:
    """Upstream PDComboBox.java: ``private static final int FLAG_EDIT = 1 << 18``."""
    assert PDComboBox.FLAG_EDIT == 1 << 18
    # And matches the consolidated PDChoice constant the dispatch path uses.
    assert PDComboBox.FLAG_EDIT == PDChoice.FLAG_EDIT


def test_combo_box_flag_edit_accessible_from_instance() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    assert cb.FLAG_EDIT == 1 << 18


# ---------- ctor: existing dictionary preserves field state ----------


def test_combo_box_from_existing_dict_preserves_combo_and_edit_flags() -> None:
    """Loading PDComboBox from a saved dict must NOT stomp /Ff."""
    field = COSDictionary()
    field.set_name(_FT, "Ch")
    # Pre-existing field flags: combo + edit + sort.
    pre_flags = (
        PDChoice.FLAG_COMBO | PDChoice.FLAG_EDIT | PDChoice.FLAG_SORT
    )
    field.set_int(_FF, pre_flags)

    form = PDAcroForm()
    cb = PDComboBox(form, field=field)

    # /Ff bits are unchanged — ctor took the existing-dict path.
    assert cb.get_field_flags() == pre_flags
    assert cb.is_combo() is True
    assert cb.is_edit() is True
    assert cb.is_sort() is True


def test_combo_box_from_existing_dict_without_combo_flag_preserved() -> None:
    """Even an inconsistent dict (Ch+no FLAG_COMBO) is preserved verbatim — the
    ctor must not retroactively set FLAG_COMBO on existing fields."""
    field = COSDictionary()
    field.set_name(_FT, "Ch")
    field.set_int(_FF, 0)  # explicitly no combo bit

    form = PDAcroForm()
    cb = PDComboBox(form, field=field)

    assert cb.is_combo() is False
    assert cb.get_field_flags() == 0


def test_combo_box_fresh_set_combo_bit_then_clears_edit_independently() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    assert cb.is_combo() is True
    assert cb.is_edit() is False
    cb.set_edit(True)
    assert cb.is_edit() is True
    assert cb.is_combo() is True
    cb.set_edit(False)
    assert cb.is_edit() is False
    assert cb.is_combo() is True


# ---------- /DV (default value) ----------


def test_combo_box_default_value_round_trip_single_string() -> None:
    """Mirrors upstream PDChoice.setDefaultValue(String) / getDefaultValue."""
    form = PDAcroForm()
    cb = PDComboBox(form)
    assert cb.get_default_value() == []

    cb.set_default_value("Apple")
    assert cb.get_default_value() == ["Apple"]
    # Confirm it landed in /DV as a single COSString (upstream stores as
    # text-string, decoded as a one-element list by the getter).
    item = cb.get_cos_object().get_dictionary_object(_DV)
    assert isinstance(item, COSString)
    assert item.get_string() == "Apple"


def test_combo_box_default_value_clear_via_none() -> None:
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_default_value("Banana")
    assert cb.get_default_value() == ["Banana"]
    cb.set_default_value(None)
    assert cb.get_default_value() == []
    assert cb.get_cos_object().get_dictionary_object(_DV) is None


def test_combo_box_default_value_reads_array_shape_from_existing_dict() -> None:
    """When /DV is a COSArray (rare for combo, common for list with
    multi-select), the getter still surfaces the values — upstream returns
    ``List<String>`` regardless."""
    field = COSDictionary()
    field.set_name(_FT, "Ch")
    field.set_int(_FF, PDChoice.FLAG_COMBO)
    field.set_item(_DV, COSArray.of_cos_strings(["X", "Y"]))

    form = PDAcroForm()
    cb = PDComboBox(form, field=field)
    assert cb.get_default_value() == ["X", "Y"]


# ---------- /V (value) edges ----------


def test_combo_box_get_value_as_string_empty_on_fresh_field() -> None:
    """Fresh combo box has no /V — Arrays.toString of an empty list is ``"[]"``."""
    form = PDAcroForm()
    cb = PDComboBox(form)
    assert cb.get_value() == []
    assert cb.get_value_as_string() == "[]"


def test_combo_box_get_value_reads_existing_v_string() -> None:
    """Loading a combo from a dict whose /V is a COSString yields a one-element
    list (upstream collapses single-string /V into a singleton list)."""
    field = COSDictionary()
    field.set_name(_FT, "Ch")
    field.set_int(_FF, PDChoice.FLAG_COMBO)
    field.set_item(_V, COSString("Cherry"))

    form = PDAcroForm()
    cb = PDComboBox(form, field=field)
    assert cb.get_value() == ["Cherry"]
    assert cb.get_value_as_string() == "[Cherry]"


def test_combo_box_set_value_none_removes_v_and_indices() -> None:
    """``set_value(None)`` clears both /V and /I — upstream parity."""
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_options(["one", "two"])
    cb.set_value("one")
    assert cb.get_value() == ["one"]

    cb.set_value(None)
    assert cb.get_value() == []
    assert cb.get_cos_object().get_dictionary_object(_V) is None
    # /I is also cleared by the underlying PDChoice.set_value(None) path.
    assert cb.get_cos_object().get_dictionary_object(
        COSName.get_pdf_name("I")
    ) is None


# ---------- editable combo: free-text path ----------


def test_combo_box_with_edit_flag_accepts_value_outside_options() -> None:
    """Editable combo (FLAG_COMBO + FLAG_EDIT) accepts free-text values that
    are not in /Opt — upstream's intent for the Edit bit. Validation only
    fires for non-edit combo boxes and list boxes."""
    form = PDAcroForm()
    cb = PDComboBox(form)
    cb.set_edit(True)
    cb.set_options(["one", "two"])

    # Free-text value outside /Opt — should not raise on editable combo.
    cb.set_value("free-text")
    assert cb.get_value() == ["free-text"]
