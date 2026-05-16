"""Tests for :meth:`PageEntry.to_string`.

Splits ``__str__`` into a public ``to_string`` that returns the upstream
``toString`` rendering, with ``__str__`` delegating to it.
"""

from __future__ import annotations

from pypdfbox.cos import COSDictionary
from pypdfbox.debugger.ui.page_entry import PageEntry


def test_to_string_without_page_label() -> None:
    entry = PageEntry(COSDictionary(), 3, None)
    assert entry.to_string() == "Page: 3"
    assert str(entry) == "Page: 3"


def test_to_string_with_page_label() -> None:
    entry = PageEntry(COSDictionary(), 5, "v-1")
    assert entry.to_string() == "Page: 5 - v-1"
    assert str(entry) == entry.to_string()


def test_to_string_with_empty_label_still_shows_dash() -> None:
    # Matches upstream: the dash is appended whenever the label is non-null,
    # even if the label happens to be the empty string.
    entry = PageEntry(COSDictionary(), 1, "")
    assert entry.to_string() == "Page: 1 - "
