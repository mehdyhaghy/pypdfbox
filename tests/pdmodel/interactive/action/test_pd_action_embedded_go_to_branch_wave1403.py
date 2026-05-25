"""Wave 1403 branch round-out for ``_resolve_named_destination``.

Closes the False-branch arrow in
``pypdfbox/pdmodel/interactive/action/pd_action_embedded_go_to.py``:

* 550->556 — the legacy ``/Dests`` lookup wrapper resolved a non-None
  ``legacy`` whose ``get_value`` returns a non-destination, but the raw
  catalog ``/Dests`` COS object is NOT a ``COSDictionary`` (e.g. it is a
  ``COSArray``), so ``isinstance(legacy_dict, COSDictionary)`` is False
  and we fall straight through to ``return None``.

Note: in normal data ``catalog.get_dests()`` only returns non-None when
``/Dests`` is itself a ``COSDictionary`` (see
``PDDocumentCatalog.get_dests``), which would make line 550 always True.
The False arm is therefore only reachable when ``get_dests`` is patched
to surface a stub while the raw ``/Dests`` value is a non-dictionary —
exactly what this test sets up. No production behaviour is changed.
"""

from __future__ import annotations

import pytest

from pypdfbox.cos import COSArray, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    _resolve_named_destination,
)


class _LegacyStub:
    """Stands in for the wrapper returned by ``catalog.get_dests()``;
    ``get_value`` yields a non-PDDestination so line 541 is False."""

    def get_value(self, _name: str) -> object | None:
        return None


def test_resolve_named_dest_legacy_dict_not_a_dictionary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes 550->556: legacy lookup is active but the raw ``/Dests``
    catalog value is a ``COSArray`` (not a ``COSDictionary``), so the
    inner isinstance arm is False and resolution returns None."""
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        # Put a NON-dictionary /Dests on the catalog so
        # get_dictionary_object("Dests") yields a COSArray at line 547.
        catalog.get_cos_object().set_item(
            COSName.get_pdf_name("Dests"), COSArray()
        )

        # Force get_dests() to return a non-None wrapper so the legacy
        # block is entered even though /Dests is not a dictionary.
        monkeypatch.setattr(
            type(catalog), "get_dests", lambda _self: _LegacyStub()
        )

        result = _resolve_named_destination(doc, "AnyName")
        assert result is None
