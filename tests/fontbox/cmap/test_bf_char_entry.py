"""Hand-written tests for ``BFCharEntry`` (pypdfbox addition)."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cmap import BFCharEntry


def test_basic_construction() -> None:
    entry = BFCharEntry(b"\x00\x41", "A")
    assert entry.get_code() == b"\x00\x41"
    assert entry.get_unicode() == "A"
    assert entry.get_code_length() == 2


def test_one_byte_code() -> None:
    entry = BFCharEntry(b"\x41", "A")
    assert entry.get_code_length() == 1


def test_four_byte_code() -> None:
    entry = BFCharEntry(b"\x00\x01\x02\x03", "X")
    assert entry.get_code_length() == 4


def test_rejects_empty_code() -> None:
    with pytest.raises(ValueError):
        BFCharEntry(b"", "A")


def test_rejects_oversized_code() -> None:
    with pytest.raises(ValueError):
        BFCharEntry(b"\x00\x01\x02\x03\x04", "A")


def test_accepts_bytearray_and_memoryview() -> None:
    entry = BFCharEntry(bytearray(b"\x00\x41"), "A")
    assert entry.get_code() == b"\x00\x41"

    entry2 = BFCharEntry(memoryview(b"\x00\x42"), "B")
    assert entry2.get_code() == b"\x00\x42"


def test_equality_and_hash() -> None:
    a = BFCharEntry(b"\x00\x41", "A")
    b = BFCharEntry(b"\x00\x41", "A")
    c = BFCharEntry(b"\x00\x41", "B")
    d = BFCharEntry(b"\x00\x42", "A")
    assert a == b
    assert a != c
    assert a != d
    assert a != "not-an-entry"
    assert hash(a) == hash(b)


def test_repr_contains_hex_and_unicode() -> None:
    entry = BFCharEntry(b"\x00\x41", "A")
    r = repr(entry)
    assert "0041" in r
    assert "'A'" in r


def test_unicode_can_be_multi_codepoint() -> None:
    """ToUnicode CMaps can map a single code to a string of codepoints."""
    entry = BFCharEntry(b"\xfb\x01", "fi")  # ligature fi -> "fi"
    assert entry.get_unicode() == "fi"
