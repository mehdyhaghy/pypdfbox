"""Hand-written tests for :class:`CFFStandardEncoding`."""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_standard_encoding import CFFStandardEncoding


def test_get_instance_is_singleton() -> None:
    a = CFFStandardEncoding.get_instance()
    b = CFFStandardEncoding.get_instance()
    assert a is b


def test_known_mappings() -> None:
    enc = CFFStandardEncoding.get_instance()
    # Cross-checked against upstream CFFStandardEncoding.java samples.
    assert enc.get_name(0) == ".notdef"
    assert enc.get_name(32) == "space"
    assert enc.get_name(112) == "p"
    assert enc.get_name(251) == "germandbls"


def test_reverse_lookup() -> None:
    enc = CFFStandardEncoding.get_instance()
    assert enc.get_code("space") == 32
    assert enc.get_code("p") == 112
    assert enc.get_code("germandbls") == 251


def test_unmapped_slots_are_notdef() -> None:
    enc = CFFStandardEncoding.get_instance()
    # Per the upstream table, code 1 maps to SID 0 -> ".notdef".
    assert enc.get_name(1) == ".notdef"


def test_full_table_size_is_256() -> None:
    enc = CFFStandardEncoding.get_instance()
    # Standard Encoding is a fixed 256-slot table; every code 0..255
    # is mapped to either a glyph name or ".notdef".
    mapping = enc.get_code_to_name_map()
    assert len(mapping) == 256
    assert all(0 <= c <= 255 for c in mapping)
