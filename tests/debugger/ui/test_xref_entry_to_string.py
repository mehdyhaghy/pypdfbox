"""Hand-written tests for :meth:`XrefEntry.to_string`.

The parity tool tracks ``toString`` as the snake-cased ``to_string``; we keep
``__str__`` delegating to it so Python idioms still work.
"""

from pypdfbox.cos import COSObjectKey
from pypdfbox.debugger.ui import XrefEntry


def test_to_string_with_offset() -> None:
    key = COSObjectKey(7, 0)
    entry = XrefEntry(0, key, 1234, None)
    assert entry.to_string() == f"Offset: 1234 [{key}]"
    assert str(entry) == entry.to_string()


def test_to_string_with_free_entry_null_key() -> None:
    entry = XrefEntry(0, None, 0, None)
    assert entry.to_string() == "(null)"
    assert str(entry) == entry.to_string()


def test_to_string_with_compressed_object_stream() -> None:
    key = COSObjectKey(8, 0)
    entry = XrefEntry(1, key, -42, None)
    assert entry.to_string() == f"Compressed object stream: 42 [{key}]"
    assert str(entry) == entry.to_string()
