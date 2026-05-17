"""Tests for ``CMapStrings``."""

from __future__ import annotations

from pypdfbox.fontbox.cmap.cmap_strings import CMapStrings


def test_get_mapping_one_byte() -> None:
    assert CMapStrings.get_mapping(b"A") == "A"


def test_get_mapping_two_byte() -> None:
    assert CMapStrings.get_mapping(b"\x00A") == "A"


def test_get_mapping_too_long_returns_none() -> None:
    assert CMapStrings.get_mapping(b"\x00\x00\x00") is None


def test_get_mapping_empty_returns_none() -> None:
    assert CMapStrings.get_mapping(b"") is None


def test_get_index_value_two_byte() -> None:
    assert CMapStrings.get_index_value(b"\x00A") == 0x0041
    assert CMapStrings.get_index_value(b"\xff\xff") == 0xFFFF


def test_get_byte_value_one_byte() -> None:
    assert CMapStrings.get_byte_value(b"A") == b"A"


def test_get_byte_value_two_byte_singleton() -> None:
    first = CMapStrings.get_byte_value(b"\x00A")
    second = CMapStrings.get_byte_value(b"\x00A")
    assert first is second


def test_get_index_value_one_byte() -> None:
    assert CMapStrings.get_index_value(b"\x10") == 0x10


def test_get_index_value_empty_returns_none() -> None:
    assert CMapStrings.get_index_value(b"") is None


def test_get_index_value_too_long_returns_none() -> None:
    assert CMapStrings.get_index_value(b"\x00\x00\x00") is None


def test_get_byte_value_empty_returns_none() -> None:
    assert CMapStrings.get_byte_value(b"") is None


def test_get_byte_value_too_long_returns_none() -> None:
    assert CMapStrings.get_byte_value(b"\x00\x00\x00") is None


def test_fill_mappings_is_noop() -> None:
    # Upstream pre-fills lazily; our port builds at import time and keeps
    # the method as a no-op for API parity.
    assert CMapStrings.fill_mappings() is None
