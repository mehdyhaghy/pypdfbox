from __future__ import annotations

from pypdfbox.fontbox.encoding import BuiltInEncoding, Encoding


def test_is_encoding_subclass() -> None:
    enc = BuiltInEncoding({})
    assert isinstance(enc, Encoding)


def test_code_to_name_round_trips() -> None:
    enc = BuiltInEncoding({65: "A", 66: "B", 32: "space"})
    assert enc.get_name(65) == "A"
    assert enc.get_name(66) == "B"
    assert enc.get_name(32) == "space"


def test_reverse_mapping_populated() -> None:
    enc = BuiltInEncoding({65: "A", 32: "space"})
    assert enc.get_code("A") == 65
    assert enc.get_code("space") == 32


def test_unmapped_code_returns_notdef() -> None:
    enc = BuiltInEncoding({65: "A"})
    assert enc.get_name(7) == ".notdef"


def test_get_codes_snapshot_is_copy() -> None:
    enc = BuiltInEncoding({65: "A"})
    codes = enc.get_codes()
    codes[66] = "B"
    # Mutating the snapshot must not leak back into the encoding.
    assert enc.get_name(66) == ".notdef"


def test_first_reverse_mapping_wins() -> None:
    # Two codes mapping to the same glyph name: ``add`` keeps the first
    # reverse mapping (Java ``Map.putIfAbsent`` semantics). dict preserves
    # insertion order, so code 1 is added first.
    enc = BuiltInEncoding({1: "A", 2: "A"})
    assert enc.get_code("A") == 1
    assert enc.get_name(1) == "A"
    assert enc.get_name(2) == "A"


def test_empty_mapping() -> None:
    enc = BuiltInEncoding({})
    assert enc.get_codes() == {}
    assert enc.get_name(0) == ".notdef"


def test_contains() -> None:
    enc = BuiltInEncoding({65: "A"})
    assert 65 in enc
    assert "A" in enc
    assert 66 not in enc
    assert "B" not in enc
