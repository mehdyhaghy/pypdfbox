"""Wave 1272: parity coverage for ``DictionaryEncoding.apply_differences``
(promoted from upstream's ``private`` no-arg helper)."""

from __future__ import annotations

from pypdfbox.cos import COSArray, COSInteger, COSName
from pypdfbox.pdmodel.font.encoding.dictionary_encoding import DictionaryEncoding


def test_apply_differences_refreshes_view_after_array_mutation() -> None:
    # Start with an empty /Differences and confirm the encoding has no
    # diff entries.
    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=COSArray(),
    )
    assert enc.get_differences() == {}

    # Mutate the underlying COSArray directly (this simulates a writer
    # that builds the array piece-by-piece without going through
    # ``set_differences``).
    diffs = enc.get_differences_array()
    assert diffs is not None
    diffs.add(COSInteger.get(65))
    diffs.add(COSName.get_pdf_name("Aacute"))

    # Without ``apply_differences`` the cached snapshot is stale.
    assert enc.get_differences() == {}

    # Calling the public helper rebuilds the differences view.
    enc.apply_differences()
    assert enc.get_differences() == {65: "Aacute"}


def test_apply_differences_handles_consecutive_runs() -> None:
    diffs = COSArray()
    diffs.add(COSInteger.get(10))
    diffs.add(COSName.get_pdf_name("a"))
    diffs.add(COSName.get_pdf_name("b"))  # implicit code 11
    diffs.add(COSName.get_pdf_name("c"))  # implicit code 12

    enc = DictionaryEncoding(
        base_encoding=COSName.get_pdf_name("WinAnsiEncoding"),
        differences=diffs,
    )
    enc.apply_differences()
    assert enc.get_differences() == {10: "a", 11: "b", 12: "c"}
