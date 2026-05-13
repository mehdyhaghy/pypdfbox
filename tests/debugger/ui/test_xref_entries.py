"""Hand-written tests for ``pypdfbox.debugger.ui.XrefEntries``."""

from pypdfbox.cos import COSObjectKey
from pypdfbox.debugger.ui import XrefEntries
from pypdfbox.pdmodel import PDDocument


def _add_xref(doc: PDDocument, num: int, gen: int, offset: int) -> COSObjectKey:
    key = COSObjectKey(num, gen)
    doc.get_document().add_xref_table({key: offset})
    return key


def test_str_is_path_constant() -> None:
    assert XrefEntries.PATH == "CRT"


def test_xref_entries_sorts_by_object_number() -> None:
    doc = PDDocument()
    try:
        # Insert out of order to prove the entries get sorted.
        k5 = _add_xref(doc, 5, 0, 500)
        k2 = _add_xref(doc, 2, 0, 200)
        k9 = _add_xref(doc, 9, 0, 900)

        entries = XrefEntries(doc)
        assert entries.get_xref_entry_count() == 3
        sorted_keys = [entries.get_xref_entry(i).get_key() for i in range(3)]
        assert sorted_keys == [k2, k5, k9]
        assert entries.get_xref_entry(0).get_index() == 0
        assert entries.get_xref_entry(2).get_index() == 2

        # ``index_of`` is the inverse of ``get_xref_entry``.
        e9 = entries.get_xref_entry(2)
        assert entries.index_of(e9) == 2
    finally:
        doc.close()


def test_str_returns_path() -> None:
    doc = PDDocument()
    try:
        entries = XrefEntries(doc)
        assert str(entries) == "CRT"
    finally:
        doc.close()
