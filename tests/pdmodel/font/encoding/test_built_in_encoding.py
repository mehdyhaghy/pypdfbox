from __future__ import annotations

import pytest

from pypdfbox.pdmodel.font.encoding import BuiltInEncoding, Encoding


def test_construction_populates_forward_map():
    enc = BuiltInEncoding({65: "A", 66: "B", 67: "C"})
    assert enc.get_name(65) == "A"
    assert enc.get_name(66) == "B"
    assert enc.get_name(67) == "C"


def test_construction_populates_reverse_map():
    enc = BuiltInEncoding({65: "A", 66: "B"})
    assert enc.get_code("A") == 65
    assert enc.get_code("B") == 66


def test_unknown_code_returns_notdef():
    enc = BuiltInEncoding({65: "A"})
    assert enc.get_name(99) == ".notdef"


def test_unknown_name_returns_none():
    enc = BuiltInEncoding({65: "A"})
    assert enc.get_code("Z") is None


def test_contains_helpers():
    enc = BuiltInEncoding({65: "A"})
    assert enc.contains_code(65)
    assert not enc.contains_code(66)
    assert enc.contains_name("A")
    assert not enc.contains_name("Z")
    assert 65 in enc
    assert "A" in enc


def test_empty_mapping():
    enc = BuiltInEncoding({})
    assert enc.get_name(0) == ".notdef"
    assert enc.get_code("A") is None
    assert enc.get_code_to_name_map() == {}


def test_encoding_name():
    enc = BuiltInEncoding({65: "A"})
    assert enc.get_encoding_name() == "built-in (TTF)"


def test_get_cos_object_unsupported():
    enc = BuiltInEncoding({65: "A"})
    with pytest.raises(NotImplementedError):
        enc.get_cos_object()


def test_inherits_from_encoding_base():
    enc = BuiltInEncoding({65: "A"})
    assert isinstance(enc, Encoding)


def test_duplicate_glyph_keeps_first_reverse_mapping():
    # Java ``Map.putIfAbsent`` semantics — the first code that maps to a glyph
    # wins for the reverse lookup.
    enc = BuiltInEncoding({65: "A", 97: "A"})
    # Forward map keeps both entries.
    assert enc.get_name(65) == "A"
    assert enc.get_name(97) == "A"
    # Reverse map keeps the first inserted code.
    assert enc.get_code("A") == 65


def test_snapshot_maps_are_copies():
    enc = BuiltInEncoding({65: "A"})
    snap = enc.get_code_to_name_map()
    snap[99] = "Z"
    # Mutating the snapshot must not affect the encoding.
    assert enc.get_name(99) == ".notdef"


def test_accepts_ordered_dict():
    # Java's ``Map`` interface is the upstream parameter type — accept any
    # ``Mapping`` so callers can pass an ``OrderedDict`` to control insertion
    # order (relevant for the reverse map's first-wins tie-break).
    from collections import OrderedDict

    od: OrderedDict[int, str] = OrderedDict()
    od[97] = "A"  # inserted first -> wins reverse mapping
    od[65] = "A"
    enc = BuiltInEncoding(od)
    assert enc.get_name(65) == "A"
    assert enc.get_name(97) == "A"
    assert enc.get_code("A") == 97


def test_accepts_mapping_proxy():
    # ``MappingProxyType`` is the canonical read-only ``Mapping`` view in
    # Python — verify the broadened parameter type accepts it.
    from types import MappingProxyType

    proxy = MappingProxyType({65: "A", 66: "B"})
    enc = BuiltInEncoding(proxy)
    assert enc.get_name(65) == "A"
    assert enc.get_code("B") == 66
