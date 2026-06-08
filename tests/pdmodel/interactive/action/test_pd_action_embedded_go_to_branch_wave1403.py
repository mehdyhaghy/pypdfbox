"""Wave 1403 branch round-out for ``_resolve_named_destination`` (retargeted
wave 1515).

Closes the False-branch arrow in
``pypdfbox/pdmodel/interactive/action/pd_action_embedded_go_to.py``:

* the legacy ``/Dests`` lookup resolved a non-None ``legacy`` wrapper, but
  its ``get_destination`` yields a non-``PDDestination`` value, so the
  ``isinstance(value, PDDestination)`` arm is False and we fall straight
  through to ``return None``.

Wave 1515 retarget: ``PDDocumentCatalog.get_dests`` now returns a
``PDDocumentNameDestinationDictionary`` (matching the upstream return type),
whose lookup method is ``get_destination`` (not the name-tree node's
``get_value``). The stub below mirrors that surface.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.interactive.action.pd_action_embedded_go_to import (
    _resolve_named_destination,
)


class _LegacyStub:
    """Stands in for the wrapper returned by ``catalog.get_dests()``;
    ``get_destination`` yields a non-PDDestination so the isinstance arm is
    False."""

    def get_destination(self, _name: str) -> object | None:
        return None


def test_resolve_named_dest_legacy_value_not_a_destination(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closes the legacy ``/Dests`` False arm: the lookup wrapper is non-None
    but its ``get_destination`` returns a non-``PDDestination``, so resolution
    returns None."""
    with PDDocument() as doc:
        catalog = doc.get_document_catalog()
        # Force get_dests() to return a non-None wrapper whose lookup yields
        # a non-destination, so the isinstance arm is False.
        monkeypatch.setattr(
            type(catalog), "get_dests", lambda _self: _LegacyStub()
        )

        result = _resolve_named_destination(doc, "AnyName")
        assert result is None
