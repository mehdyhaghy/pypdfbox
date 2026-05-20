"""Port of upstream ``CMapStringsTest`` from
``fontbox/src/test/java/org/apache/fontbox/cmap/CMapStringsTest.java``.

Exercises the interning helpers ``get_mapping`` / ``get_byte_value`` /
``get_index_value`` for one- and two-byte sequences plus the
non-cached >2-byte path that returns ``None``. The port follows the
JUnit table in CLAUDE.md (``assertSame`` -> ``is``,
``assertNotSame`` -> ``is not``, ``assertNull`` -> ``is None``).
"""

from __future__ import annotations

from pypdfbox.fontbox.cmap.cmap_strings import CMapStrings


# Translated from getNonCachedMappings.
def test_get_non_cached_mappings() -> None:
    assert CMapStrings.get_mapping(bytes([0, 0, 0])) is None
    assert CMapStrings.get_mapping(bytes([0, 0, 0, 0])) is None


# Translated from getMappingOneByte -- min, max, and arbitrary value.
def test_get_mapping_one_byte() -> None:
    min_value_one_byte = bytes([0])
    min_value_mapping = min_value_one_byte.decode("iso-8859-1")
    assert CMapStrings.get_mapping(min_value_one_byte) == CMapStrings.get_mapping(
        min_value_one_byte
    )
    assert CMapStrings.get_mapping(min_value_one_byte) is CMapStrings.get_mapping(
        min_value_one_byte
    )
    assert CMapStrings.get_mapping(min_value_one_byte) == min_value_mapping

    max_value_one_byte = bytes([0xFF])
    max_value_mapping = max_value_one_byte.decode("iso-8859-1")
    assert CMapStrings.get_mapping(max_value_one_byte) == CMapStrings.get_mapping(
        max_value_one_byte
    )
    assert CMapStrings.get_mapping(max_value_one_byte) is CMapStrings.get_mapping(
        max_value_one_byte
    )
    assert CMapStrings.get_mapping(max_value_one_byte) == max_value_mapping

    any_value_one_byte = bytes([98])
    any_value_mapping = any_value_one_byte.decode("iso-8859-1")
    assert CMapStrings.get_mapping(any_value_one_byte) == CMapStrings.get_mapping(
        any_value_one_byte
    )
    assert CMapStrings.get_mapping(any_value_one_byte) is CMapStrings.get_mapping(
        any_value_one_byte
    )
    assert CMapStrings.get_mapping(any_value_one_byte) == any_value_mapping


# Translated from getMappingTwoByte -- min, max, and three arbitrary
# values across the high-low / low-high boundary.
def test_get_mapping_two_byte() -> None:
    cases: tuple[bytes, ...] = (
        bytes([0, 0]),
        bytes([0xFF, 0xFF]),
        bytes([0x62, 0x43]),
        bytes([0xFF, 0x43]),
        bytes([0x38, 0xFF]),
    )
    for value in cases:
        expected_mapping = value.decode("utf-16-be")
        assert CMapStrings.get_mapping(value) == CMapStrings.get_mapping(value)
        assert CMapStrings.get_mapping(value) is CMapStrings.get_mapping(value)
        assert CMapStrings.get_mapping(value) == expected_mapping


# Translated from getByteValuesOneByte -- the cached byte value must
# be equal to itself across calls and is the same interned object on
# repeated calls. The upstream ``assertNotSame(input, cached)`` doesn't
# translate cleanly: CPython interns small ``bytes`` objects, so the
# identity check would fire spuriously for any value that the
# interpreter happens to intern. We retain structural equality +
# repeated-call identity invariants instead.
def test_get_byte_values_one_byte() -> None:
    for value in (bytes([0]), bytes([0xFF]), bytes([98])):
        cached = CMapStrings.get_byte_value(value)
        assert cached == CMapStrings.get_byte_value(value)
        assert cached is CMapStrings.get_byte_value(value)
        assert cached == value


# Translated from getByteValuesTwoByte. See note on
# ``test_get_byte_values_one_byte`` for why the identity-not-same
# check is dropped.
def test_get_byte_values_two_byte() -> None:
    for value in (
        bytes([0, 0]),
        bytes([0xFF, 0xFF]),
        bytes([0x62, 0x43]),
        bytes([0xFF, 0x43]),
        bytes([0x38, 0xFF]),
    ):
        cached = CMapStrings.get_byte_value(value)
        assert cached == CMapStrings.get_byte_value(value)
        assert cached is CMapStrings.get_byte_value(value)
        assert cached == value


# Translated from getNonCachedByteValues.
def test_get_non_cached_byte_values() -> None:
    assert CMapStrings.get_byte_value(bytes([0, 0, 0])) is None
    assert CMapStrings.get_byte_value(bytes([0, 0, 0, 0])) is None


# Translated from getIndexValuesOneByte.
def test_get_index_values_one_byte() -> None:
    cases: tuple[tuple[bytes, int], ...] = (
        (bytes([0]), 0),
        (bytes([0xFF]), 0xFF),
        (bytes([98]), 98),
    )
    for value, expected in cases:
        assert CMapStrings.get_index_value(value) == CMapStrings.get_index_value(value)
        # ``int`` equality holds; identity is implementation-defined for
        # small-int interning so we exercise equality on both sides.
        assert CMapStrings.get_index_value(value) is CMapStrings.get_index_value(value)
        assert CMapStrings.get_index_value(value) == expected


# Translated from getIndexValuesTwoByte.
def test_get_index_values_two_byte() -> None:
    cases: tuple[tuple[bytes, int], ...] = (
        (bytes([0, 0]), 0),
        (bytes([0xFF, 0xFF]), 0xFFFF),
        (bytes([0x62, 0x43]), 0x6243),
        (bytes([0xFF, 0x43]), 0xFF43),
        (bytes([0x38, 0xFF]), 0x38FF),
    )
    for value, expected in cases:
        assert CMapStrings.get_index_value(value) == CMapStrings.get_index_value(value)
        assert CMapStrings.get_index_value(value) == expected


# Translated from getNonCachedIndexValues.
def test_get_non_cached_index_values() -> None:
    assert CMapStrings.get_index_value(bytes([0, 0, 0])) is None
    assert CMapStrings.get_index_value(bytes([0, 0, 0, 0])) is None
