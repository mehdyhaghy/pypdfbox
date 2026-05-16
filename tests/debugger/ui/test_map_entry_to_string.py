"""Tests for ``MapEntry.to_string`` (wave 1312)."""

from __future__ import annotations

from pypdfbox.cos import COSInteger, COSName
from pypdfbox.debugger.ui import MapEntry


def test_to_string_returns_key_name_when_set() -> None:
    """When a key is set, ``to_string`` returns its name."""

    entry = MapEntry()
    entry.set_key(COSName.get_pdf_name("Type"))
    assert entry.to_string() == "Type"


def test_to_string_returns_placeholder_for_unset_key() -> None:
    """When no key has been assigned, ``to_string`` returns ``"(null)"``,
    matching upstream's ``toString`` placeholder."""

    entry = MapEntry()
    assert entry.to_string() == "(null)"
    # Even after value/item are populated, missing key still yields "(null)".
    entry.set_value(COSInteger.get(5))
    entry.set_item(COSInteger.get(6))
    assert entry.to_string() == "(null)"


def test_dunder_str_delegates_to_to_string() -> None:
    """``str(entry)`` and ``entry.to_string()`` agree in every state."""

    entry = MapEntry()
    assert str(entry) == entry.to_string()
    entry.set_key(COSName.get_pdf_name("Length"))
    assert str(entry) == entry.to_string() == "Length"
