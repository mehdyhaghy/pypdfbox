"""Port of upstream ``PDOutlineItemTest`` (PDFBox 3.0.x).

Source: ``pdfbox/src/test/java/org/apache/pdfbox/pdmodel/interactive/
documentnavigation/outline/PDOutlineItemTest.java``.

Covers sibling-insertion (``insert_sibling_after`` / ``insert_sibling_before``)
with every combination of open/closed parent and open/closed inserted child,
plus head/tail insertion edge cases and the no-parent rejection invariant.
"""

from __future__ import annotations

import pytest

from pypdfbox.pdmodel.interactive.documentnavigation.outline import PDOutlineItem


@pytest.fixture
def fixture() -> dict[str, PDOutlineItem]:
    root = PDOutlineItem()
    first = PDOutlineItem()
    second = PDOutlineItem()
    root.add_last(first)
    root.add_last(second)
    new_sibling = PDOutlineItem()
    new_sibling.add_last(PDOutlineItem())
    new_sibling.add_last(PDOutlineItem())
    return {
        "root": root,
        "first": first,
        "second": second,
        "new_sibling": new_sibling,
    }


def test_insert_sibling_after_open_child_to_open_parent(fixture: dict[str, PDOutlineItem]) -> None:
    root, first, second, new_sibling = (
        fixture["root"],
        fixture["first"],
        fixture["second"],
        fixture["new_sibling"],
    )
    new_sibling.open_node()
    root.open_node()
    assert root.get_open_count() == 2
    first.insert_sibling_after(new_sibling)
    assert first.get_next_sibling() == new_sibling
    assert second.get_previous_sibling() == new_sibling
    assert root.get_open_count() == 5


def test_insert_sibling_before_open_child_to_open_parent(fixture: dict[str, PDOutlineItem]) -> None:
    root, first, second, new_sibling = (
        fixture["root"],
        fixture["first"],
        fixture["second"],
        fixture["new_sibling"],
    )
    new_sibling.open_node()
    root.open_node()
    assert root.get_open_count() == 2
    second.insert_sibling_before(new_sibling)
    assert first.get_next_sibling() == new_sibling
    assert second.get_previous_sibling() == new_sibling
    assert root.get_open_count() == 5


def test_insert_sibling_after_open_child_to_closed_parent(
    fixture: dict[str, PDOutlineItem],
) -> None:
    root, first, second, new_sibling = (
        fixture["root"],
        fixture["first"],
        fixture["second"],
        fixture["new_sibling"],
    )
    new_sibling.open_node()
    assert root.get_open_count() == -2
    first.insert_sibling_after(new_sibling)
    assert first.get_next_sibling() == new_sibling
    assert second.get_previous_sibling() == new_sibling
    assert root.get_open_count() == -5


def test_insert_sibling_before_open_child_to_closed_parent(
    fixture: dict[str, PDOutlineItem],
) -> None:
    root, first, second, new_sibling = (
        fixture["root"],
        fixture["first"],
        fixture["second"],
        fixture["new_sibling"],
    )
    new_sibling.open_node()
    assert root.get_open_count() == -2
    second.insert_sibling_before(new_sibling)
    assert first.get_next_sibling() == new_sibling
    assert second.get_previous_sibling() == new_sibling
    assert root.get_open_count() == -5


def test_insert_sibling_after_closed_child_to_open_parent(
    fixture: dict[str, PDOutlineItem],
) -> None:
    root, first, second, new_sibling = (
        fixture["root"],
        fixture["first"],
        fixture["second"],
        fixture["new_sibling"],
    )
    root.open_node()
    assert root.get_open_count() == 2
    first.insert_sibling_after(new_sibling)
    assert first.get_next_sibling() == new_sibling
    assert second.get_previous_sibling() == new_sibling
    assert root.get_open_count() == 3


def test_insert_sibling_before_closed_child_to_open_parent(
    fixture: dict[str, PDOutlineItem],
) -> None:
    root, first, second, new_sibling = (
        fixture["root"],
        fixture["first"],
        fixture["second"],
        fixture["new_sibling"],
    )
    root.open_node()
    assert root.get_open_count() == 2
    second.insert_sibling_before(new_sibling)
    assert first.get_next_sibling() == new_sibling
    assert second.get_previous_sibling() == new_sibling
    assert root.get_open_count() == 3


def test_insert_sibling_after_closed_child_to_closed_parent(
    fixture: dict[str, PDOutlineItem],
) -> None:
    root, first, second, new_sibling = (
        fixture["root"],
        fixture["first"],
        fixture["second"],
        fixture["new_sibling"],
    )
    assert root.get_open_count() == -2
    first.insert_sibling_after(new_sibling)
    assert first.get_next_sibling() == new_sibling
    assert second.get_previous_sibling() == new_sibling
    assert root.get_open_count() == -3


def test_insert_sibling_before_closed_child_to_closed_parent(
    fixture: dict[str, PDOutlineItem],
) -> None:
    root, first, second, new_sibling = (
        fixture["root"],
        fixture["first"],
        fixture["second"],
        fixture["new_sibling"],
    )
    assert root.get_open_count() == -2
    second.insert_sibling_before(new_sibling)
    assert first.get_next_sibling() == new_sibling
    assert second.get_previous_sibling() == new_sibling
    assert root.get_open_count() == -3


def test_insert_sibling_top(fixture: dict[str, PDOutlineItem]) -> None:
    root, first = fixture["root"], fixture["first"]
    assert root.get_first_child() == first
    new_sibling = PDOutlineItem()
    first.insert_sibling_before(new_sibling)
    assert first.get_previous_sibling() == new_sibling
    assert root.get_first_child() == new_sibling


def test_insert_sibling_top_no_parent(fixture: dict[str, PDOutlineItem]) -> None:
    root, first = fixture["root"], fixture["first"]
    assert root.get_first_child() == first
    new_sibling = PDOutlineItem()
    root.insert_sibling_before(new_sibling)
    assert root.get_previous_sibling() == new_sibling


def test_insert_sibling_bottom(fixture: dict[str, PDOutlineItem]) -> None:
    root, second = fixture["root"], fixture["second"]
    assert root.get_last_child() == second
    new_sibling = PDOutlineItem()
    second.insert_sibling_after(new_sibling)
    assert second.get_next_sibling() == new_sibling
    assert root.get_last_child() == new_sibling


def test_insert_sibling_bottom_no_parent(fixture: dict[str, PDOutlineItem]) -> None:
    root, second = fixture["root"], fixture["second"]
    assert root.get_last_child() == second
    new_sibling = PDOutlineItem()
    root.insert_sibling_after(new_sibling)
    assert root.get_next_sibling() == new_sibling


def test_cannot_insert_sibling_before_a_list(fixture: dict[str, PDOutlineItem]) -> None:
    root = fixture["root"]
    child = PDOutlineItem()
    child.insert_sibling_after(PDOutlineItem())
    child.insert_sibling_after(PDOutlineItem())
    with pytest.raises(ValueError):
        root.insert_sibling_before(child)


def test_cannot_insert_sibling_after_a_list(fixture: dict[str, PDOutlineItem]) -> None:
    root = fixture["root"]
    child = PDOutlineItem()
    child.insert_sibling_after(PDOutlineItem())
    child.insert_sibling_after(PDOutlineItem())
    with pytest.raises(ValueError):
        root.insert_sibling_after(child)
