from __future__ import annotations

from pypdfbox.pdmodel.interactive.action import PDActionURI
from pypdfbox.pdmodel.interactive.documentnavigation.destination import (
    PDPageFitDestination,
)
from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem


def test_outline_item_typed_destination_round_trip() -> None:
    item = PDOutlineItem()
    dest = PDPageFitDestination()
    dest.set_page_number(1)

    item.set_destination(dest)
    resolved = item.get_destination()

    assert isinstance(resolved, PDPageFitDestination)
    assert resolved.get_page_number() == 1


def test_outline_item_typed_action_round_trip() -> None:
    item = PDOutlineItem()
    action = PDActionURI()
    action.set_uri("https://example.test")

    item.set_action(action)
    resolved = item.get_action()

    assert isinstance(resolved, PDActionURI)
    assert resolved.get_uri() == "https://example.test"
