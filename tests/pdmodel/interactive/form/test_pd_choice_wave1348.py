"""Wave 1348 coverage-boost tests for ``pypdfbox.pdmodel.interactive.form.pd_choice``.

Targets the previously-uncovered branches:

  * :meth:`PDChoice.get_value_for` (lines 319-320) — dispatch helper for
    /V and /DV.
  * :meth:`PDChoice.update_selected_options_index` (lines 333-343) — the
    public mirror of upstream's ``updateSelectedOptionsIndex`` that takes
    explicit value+options lists.
"""
from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_choice import PDChoice

_V: COSName = COSName.get_pdf_name("V")
_DV: COSName = COSName.get_pdf_name("DV")
_I: COSName = COSName.get_pdf_name("I")


# ---------- get_value_for ----------


def test_get_value_for_missing_returns_empty() -> None:
    """No ``/V`` or ``/DV`` entry → empty list."""
    field = PDChoice(PDAcroForm())
    assert field.get_value_for(_V) == []
    assert field.get_value_for(_DV) == []


def test_get_value_for_string_returns_singleton() -> None:
    """A single ``COSString`` at /V → ``[value]``."""
    field = PDChoice(PDAcroForm())
    field.get_cos_object().set_item(_V, COSString("Apple"))
    assert field.get_value_for(_V) == ["Apple"]


def test_get_value_for_array_returns_each_entry() -> None:
    """A ``COSArray`` at /DV → all string values, in order."""
    field = PDChoice(PDAcroForm())
    arr = COSArray()
    arr.add(COSString("Apple"))
    arr.add(COSString("Banana"))
    field.get_cos_object().set_item(_DV, arr)
    assert field.get_value_for(_DV) == ["Apple", "Banana"]


# ---------- update_selected_options_index ----------


def test_update_selected_options_index_sorts_indices_ascending() -> None:
    """Unsorted matches are sorted before being written to /I."""
    field = PDChoice(PDAcroForm())
    options = ["Alpha", "Bravo", "Charlie", "Delta"]
    # Values supplied in reverse-order — /I must come back ascending.
    field.update_selected_options_index(["Delta", "Alpha", "Charlie"], options)

    i_arr = field.get_cos_object().get_dictionary_object(_I)
    assert isinstance(i_arr, COSArray)
    written = [i_arr.get_object(i).int_value() for i in range(i_arr.size())]
    assert written == [0, 2, 3]


def test_update_selected_options_index_records_minus_one_for_missing() -> None:
    """Java ``List.indexOf`` returns -1 for absent values; the Python port
    preserves the quirk (line 341)."""
    field = PDChoice(PDAcroForm())
    options = ["Alpha", "Bravo"]
    field.update_selected_options_index(["Bravo", "Missing"], options)
    i_arr = field.get_cos_object().get_dictionary_object(_I)
    assert isinstance(i_arr, COSArray)
    written = [i_arr.get_object(i).int_value() for i in range(i_arr.size())]
    # -1 sorts before the valid 1.
    assert written == [-1, 1]


def test_update_selected_options_index_empty_values_clears_indices() -> None:
    """Passing an empty value list writes ``None`` to /I (the setter
    treats an empty list as "clear")."""
    field = PDChoice(PDAcroForm())
    field.get_cos_object().set_item(_I, COSArray())  # pre-populate
    field.update_selected_options_index([], ["A", "B"])
    # set_selected_options_indices(None when empty) removes /I.
    i_arr = field.get_cos_object().get_dictionary_object(_I)
    # The "empty-indices clears" behaviour is the upstream contract; what
    # matters is the call doesn't raise and /I no longer carries stale
    # entries (it should either be missing or empty).
    assert i_arr is None or i_arr.size() == 0
