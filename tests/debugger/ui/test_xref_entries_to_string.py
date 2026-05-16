"""Tests for :meth:`XrefEntries.to_string`.

Splits ``__str__`` into a public ``to_string`` that returns the upstream
``toString`` rendering — the ``CRT`` path constant.
"""

from __future__ import annotations

from pypdfbox.debugger.ui import XrefEntries
from pypdfbox.pdmodel import PDDocument


def test_to_string_returns_path_constant() -> None:
    doc = PDDocument()
    try:
        entries = XrefEntries(doc)
        assert entries.to_string() == "CRT"
    finally:
        doc.close()


def test_str_delegates_to_to_string() -> None:
    doc = PDDocument()
    try:
        entries = XrefEntries(doc)
        assert str(entries) == entries.to_string()
    finally:
        doc.close()


def test_to_string_matches_path_attribute() -> None:
    doc = PDDocument()
    try:
        entries = XrefEntries(doc)
        assert entries.to_string() == XrefEntries.PATH
    finally:
        doc.close()
