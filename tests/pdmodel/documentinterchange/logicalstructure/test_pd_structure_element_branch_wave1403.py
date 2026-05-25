"""Wave 1403 branch round-out for
``PDStructureElement.get_class_names_as_strings``.

Closes the False-branch arrow in
``pypdfbox/pdmodel/documentinterchange/logicalstructure/pd_structure_element.py``:

* 737->733 — a ``/C`` revisions entry is neither a ``COSName`` nor a
  Python ``str`` (e.g. a stray ``COSInteger`` value slot), so both the
  ``isinstance(entry, COSName)`` and ``elif isinstance(entry, str)`` arms
  are False and the loop simply advances to the next entry, skipping it.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.documentinterchange.logicalstructure.pd_structure_element import (
    PDStructureElement,
)


def test_get_class_names_as_strings_skips_non_name_non_str_entry() -> None:
    """Closes 737->733: a ``/C`` array holding a single ``COSInteger``
    value (no trailing revision int) decodes as one entry that is neither
    a COSName nor a str, so it is skipped and the result is empty."""
    elem = PDStructureElement("Sect")
    # Single-element /C array: a bare COSInteger value with no following
    # revision integer, so Revisions reads it as one entry.
    c = COSArray()
    c.add(COSInteger.get(42))
    elem.get_cos_object().set_item(COSName.get_pdf_name("C"), c)

    names = elem.get_class_names_as_strings()
    assert names == []


def test_get_class_names_as_strings_keeps_real_name_entry() -> None:
    """Companion: a genuine COSName entry is decoded (covers the True arm
    at 735->736 so the skip case stands out)."""
    elem = PDStructureElement("Sect")
    elem.get_cos_object().set_name(COSName.get_pdf_name("C"), "myclass")

    names = elem.get_class_names_as_strings()
    assert names == ["myclass"]
