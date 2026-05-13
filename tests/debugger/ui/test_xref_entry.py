"""Hand-written tests for ``pypdfbox.debugger.ui.XrefEntry``."""

from pypdfbox.cos import COSInteger, COSObject, COSObjectKey
from pypdfbox.debugger.ui import XrefEntries, XrefEntry


def test_str_with_offset() -> None:
    key = COSObjectKey(7, 0)
    entry = XrefEntry(0, key, 1234, None)
    assert str(entry) == f"Offset: 1234 [{key}]"
    assert entry.get_path() == f"{XrefEntries.PATH}/{entry}"


def test_str_with_compressed_offset() -> None:
    key = COSObjectKey(8, 0)
    entry = XrefEntry(1, key, -42, None)
    assert str(entry) == f"Compressed object stream: 42 [{key}]"


def test_null_key_renders_placeholder() -> None:
    entry = XrefEntry(0, None, 0, None)
    assert str(entry) == "(null)"


def test_get_object_dereferences_cos_object() -> None:
    target = COSInteger.get(123)
    obj = COSObject(9, 0, resolved=target)
    entry = XrefEntry(0, COSObjectKey(9, 0), 0, obj)
    assert entry.get_cos_object() is obj
    assert entry.get_object() is target


def test_get_object_returns_none_when_cos_object_missing() -> None:
    entry = XrefEntry(0, COSObjectKey(9, 0), 0, None)
    assert entry.get_object() is None
