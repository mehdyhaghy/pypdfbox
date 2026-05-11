"""Tests for :mod:`pypdfbox.pdmodel.font.cid_system_info`.

No upstream JUnit test exists — :class:`CIDSystemInfo` is a value class
exercised only via ``FontInfo`` integration tests. We cover the three
field accessors plus ``toString()`` / ``__eq__`` / ``__hash__``.
"""

from __future__ import annotations

from pypdfbox.pdmodel.font.cid_system_info import CIDSystemInfo


def test_constructor_round_trip() -> None:
    info = CIDSystemInfo("Adobe", "Japan1", 6)
    assert info.get_registry() == "Adobe"
    assert info.get_ordering() == "Japan1"
    assert info.get_supplement() == 6


def test_to_string_matches_upstream_format() -> None:
    info = CIDSystemInfo("Adobe", "Japan1", 6)
    # Upstream toString returns "R-O-S" (CIDSystemInfo.java line 53-57).
    assert str(info) == "Adobe-Japan1-6"


def test_structural_equality() -> None:
    a = CIDSystemInfo("Adobe", "GB1", 4)
    b = CIDSystemInfo("Adobe", "GB1", 4)
    c = CIDSystemInfo("Adobe", "GB1", 5)
    assert a == b
    assert hash(a) == hash(b)
    assert a != c
    assert a != "not a CIDSystemInfo"


def test_repr_contains_all_fields() -> None:
    info = CIDSystemInfo("Adobe", "Identity", 0)
    text = repr(info)
    assert "Adobe" in text
    assert "Identity" in text
    assert "0" in text
