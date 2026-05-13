"""Hand-written tests for ``pypdfbox.debugger.ui.ArrayEntry``."""

from pypdfbox.cos import COSInteger
from pypdfbox.debugger.ui import ArrayEntry


def test_defaults() -> None:
    entry = ArrayEntry()
    assert entry.get_index() == 0
    assert entry.get_value() is None
    assert entry.get_item() is None


def test_round_trip() -> None:
    entry = ArrayEntry()
    entry.set_index(7)
    value = COSInteger.get(42)
    item = COSInteger.get(99)
    entry.set_value(value)
    entry.set_item(item)
    assert entry.get_index() == 7
    assert entry.get_value() is value
    assert entry.get_item() is item


def test_value_and_item_are_independent() -> None:
    entry = ArrayEntry()
    entry.set_value(COSInteger.get(1))
    entry.set_item(COSInteger.get(2))
    assert entry.get_value().int_value() == 1
    assert entry.get_item().int_value() == 2
