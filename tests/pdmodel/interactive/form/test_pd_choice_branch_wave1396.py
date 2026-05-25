"""Wave 1396 branch-coverage tests for ``PDChoice.get_options``
and ``get_options_display_values``.

Closes False-branch arrows where an /Opt entry's first/second element
returns ``None`` from ``_entry_to_str`` (because the COS value isn't a
string or name):

* 145->140, 149->140 — get_options inner branches when entry is not
  coercible to a string
* 231->226, 236->226, 240->226 — get_options_display_values inner
  branches when the entry is not coercible to a string
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName, COSString
from pypdfbox.pdmodel.interactive.form.pd_combo_box import PDComboBox
from pypdfbox.pdmodel.pd_document import PDDocument


def _choice_field(opt_array: COSArray) -> PDComboBox:
    with PDDocument() as document:
        from pypdfbox.pdmodel.interactive.form.pd_acro_form import PDAcroForm

        form = PDAcroForm(document)
        document.get_document_catalog().set_acro_form(form)
        field = PDComboBox(form)
        field.get_cos_object().set_item("Opt", opt_array)
        return field


def test_get_options_skips_non_coercible_first_entry_in_pair() -> None:
    """Pair-form entry whose first element is non-string/name is filtered out.

    Closes False arms at line 145->140 (first not coercible).
    """
    opt = COSArray()
    pair_bad = COSArray()
    pair_bad.add(COSInteger.get(99))  # not coercible
    pair_bad.add(COSString("Display"))
    opt.add(pair_bad)
    pair_ok = COSArray()
    pair_ok.add(COSString("real-export"))
    pair_ok.add(COSString("real-display"))
    opt.add(pair_ok)
    field = _choice_field(opt)
    assert field.get_options() == ["real-export"]


def test_get_options_skips_non_coercible_flat_entry() -> None:
    """Flat entry (non-pair, non-string/name) is filtered out.

    Closes False arm at line 149->140.
    """
    opt = COSArray()
    opt.add(COSInteger.get(99))  # flat non-coercible
    opt.add(COSString("real"))
    field = _choice_field(opt)
    assert field.get_options() == ["real"]


def test_get_options_display_values_skips_non_coercible_second_entry() -> None:
    """Pair where second element is non-string/name is filtered out.

    Closes False arm at line 231->226.
    """
    opt = COSArray()
    pair_bad = COSArray()
    pair_bad.add(COSString("export"))
    pair_bad.add(COSInteger.get(99))  # display side not coercible
    opt.add(pair_bad)
    field = _choice_field(opt)
    assert field.get_options_display_values() == []


def test_get_options_display_values_skips_non_coercible_first_for_one_elem_pair() -> None:
    """Single-element pair where the first isn't coercible is filtered.

    Closes False arm at line 236->226 (entry.size()==1 branch returns None).
    """
    opt = COSArray()
    pair_solo = COSArray()
    pair_solo.add(COSInteger.get(99))  # not coercible
    opt.add(pair_solo)
    field = _choice_field(opt)
    assert field.get_options_display_values() == []


def test_get_options_display_values_skips_non_coercible_flat_entry() -> None:
    """Flat non-pair, non-coercible entry is filtered out.

    Closes False arm at line 240->226.
    """
    opt = COSArray()
    opt.add(COSInteger.get(99))
    opt.add(COSName.get_pdf_name("Visible"))
    field = _choice_field(opt)
    # The COSName is coercible (name), so it shows up; integer is dropped.
    assert field.get_options_display_values() == ["Visible"]
