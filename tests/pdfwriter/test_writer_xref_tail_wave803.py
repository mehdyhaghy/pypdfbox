from __future__ import annotations

from pypdfbox.cos import COSObjectKey
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry


def test_xref_entry_le_ge_compare_by_object_number_only() -> None:
    first = COSWriterXRefEntry(offset=99, key=COSObjectKey(3, 0), free=True)
    same_object = COSWriterXRefEntry(offset=1, key=COSObjectKey(3, 7))
    later = COSWriterXRefEntry(offset=0, key=COSObjectKey(5, 0))

    assert first <= same_object
    assert first >= same_object
    assert first <= later
    assert later >= first

