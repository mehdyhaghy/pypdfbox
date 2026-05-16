"""Hand-written tests for :meth:`DocumentEntry.to_string`.

The parity tool tracks ``toString`` as the snake-cased ``to_string``; we keep
``__str__`` delegating to it so Python idioms still work.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from pypdfbox.debugger.ui.document_entry import DocumentEntry


def test_to_string_returns_filename() -> None:
    entry = DocumentEntry(MagicMock(), "sample.pdf")
    assert entry.to_string() == "sample.pdf"


def test_str_delegates_to_to_string() -> None:
    entry = DocumentEntry(MagicMock(), "another.pdf")
    assert str(entry) == entry.to_string()


def test_to_string_empty_filename() -> None:
    entry = DocumentEntry(MagicMock(), "")
    assert entry.to_string() == ""
    assert str(entry) == ""
