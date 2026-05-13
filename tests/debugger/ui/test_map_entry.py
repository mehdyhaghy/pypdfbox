"""Hand-written tests for ``pypdfbox.debugger.ui.MapEntry``."""

from pypdfbox.cos import COSInteger, COSName
from pypdfbox.debugger.ui import MapEntry


def test_defaults() -> None:
    entry = MapEntry()
    assert entry.get_key() is None
    assert entry.get_value() is None
    assert entry.get_item() is None
    assert str(entry) == "(null)"


def test_round_trip() -> None:
    entry = MapEntry()
    key = COSName.get_pdf_name("Foo")
    value = COSInteger.get(5)
    item = COSInteger.get(6)
    entry.set_key(key)
    entry.set_value(value)
    entry.set_item(item)
    assert entry.get_key() is key
    assert entry.get_value() is value
    assert entry.get_item() is item


def test_str_uses_key_name() -> None:
    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Type"))
    assert str(entry) == "Type"
