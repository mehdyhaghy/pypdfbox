"""Wave 1403 branch round-out for ``PDActionSubmitForm.get_fields``.

Closes the True-branch arrow in
``pypdfbox/pdmodel/interactive/action/pd_action_submit_form.py``:

* 163->166 — a ``/Fields`` array entry is a ``COSString`` (a
  fully-qualified field name that cannot be resolved without an
  AcroForm), so the ``elif isinstance(entry, COSString)`` arm fires and
  the loop ``continue``s, dropping that entry from the typed result.
"""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSName, COSString
from pypdfbox.pdmodel.interactive.action.pd_action_submit_form import (
    PDActionSubmitForm,
)


def test_get_fields_skips_cos_string_entry() -> None:
    """Closes 163->166: a COSString /Fields entry (a partial field name)
    is skipped via ``continue`` because it can't be resolved here."""
    action = PDActionSubmitForm()
    fields = COSArray()
    fields.add(COSString("topmostSubform[0].Page1[0].Name[0]"))
    action.get_cos_object().set_item(COSName.get_pdf_name("Fields"), fields)

    result = action.get_fields()
    # The lone string entry was dropped -> empty typed list.
    assert result == []
