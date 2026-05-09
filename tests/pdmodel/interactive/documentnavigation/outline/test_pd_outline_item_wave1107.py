from __future__ import annotations

from typing import Any

from tests.pdmodel.interactive.documentnavigation.outline import (
    test_pd_outline_item_wave450 as wave450,
)


def test_wave450_name_tree_fake_catalog_dests_fallback_is_exercised(
    monkeypatch: Any,
) -> None:
    def resolve_via_legacy_dests(document: Any, named_destination: Any) -> Any:
        assert named_destination.get_named_destination() == "chapter"
        assert document.get_document_catalog().get_dests() is None

        destination = wave450.PDPageFitDestination()
        destination.set_page_number(3)
        return destination

    monkeypatch.setattr(
        wave450.PDOutlineItem,
        "_resolve_named_destination",
        staticmethod(resolve_via_legacy_dests),
    )

    wave450.test_resolve_named_destination_unwraps_name_tree_dictionary_entry()
