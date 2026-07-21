"""PDFBOX-6207 (upstream 3.0.8): empty ``COSString`` /Opt yields an EMPTY list.

Upstream ``PDButton.getExportValues`` returns ``Collections.emptyList()``
when the inheritable ``/Opt`` entry is a ``COSString`` whose string value is
empty; a non-empty single string still yields a singleton list and array
entries are unaffected.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.form import PDAcroForm
from pypdfbox.pdmodel.interactive.form.pd_check_box import PDCheckBox

_OPT = COSName.get_pdf_name("Opt")


def test_empty_cos_string_opt_yields_empty_export_values() -> None:
    box = PDCheckBox(PDAcroForm())
    box.get_cos_object().set_item(_OPT, COSString(""))

    assert box.get_export_values() == []


def test_non_empty_cos_string_opt_still_yields_singleton_list() -> None:
    box = PDCheckBox(PDAcroForm())
    box.get_cos_object().set_item(_OPT, COSString("single"))

    assert box.get_export_values() == ["single"]


def test_array_opt_entries_unaffected_including_empty_strings() -> None:
    """The PDFBOX-6207 empty-string guard applies only to the top-level
    ``COSString`` /Opt shape; array entries pass through unchanged (upstream
    ``COSArray.toCOSStringStringList`` keeps empty strings)."""
    box = PDCheckBox(PDAcroForm())
    arr = COSArray()
    arr.add(COSString("first"))
    arr.add(COSString(""))
    arr.add(COSString("third"))
    box.get_cos_object().set_item(_OPT, arr)

    assert box.get_export_values() == ["first", "", "third"]
