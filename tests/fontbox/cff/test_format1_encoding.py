"""Hand-written tests for :class:`Format1Encoding` and :class:`Range3`."""

from __future__ import annotations

import dataclasses

from pypdfbox.fontbox.cff.cff_built_in_encoding import Supplement
from pypdfbox.fontbox.cff.format1_encoding import Format1Encoding, Range3


def test_range3_default_sid_is_minus_one() -> None:
    r = Range3(first=10, n_left=4)
    assert r.first == 10
    assert r.n_left == 4
    assert r.sid == -1


def test_range3_explicit_sid() -> None:
    r = Range3(first=10, n_left=4, sid=99)
    assert r.sid == 99


def test_range3_repr() -> None:
    r = Range3(first=1, n_left=2, sid=3)
    assert repr(r) == "Range3[first=1, n_left=2, sid=3]"


def test_range3_is_frozen() -> None:
    r = Range3(first=0, n_left=0)
    try:
        r.first = 99  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("Range3 should be frozen")


def test_n_ranges_is_stored() -> None:
    enc = Format1Encoding(5)
    assert enc.n_ranges == 5


def test_inherits_built_in_encoding_methods() -> None:
    enc = Format1Encoding(1)
    enc.add(0, 0, ".notdef")
    enc.add(1, 1, "space")
    assert enc.get_name(0) == ".notdef"
    assert enc.get_name(1) == "space"


def test_repr_includes_n_ranges_and_supplement() -> None:
    enc = Format1Encoding(2)
    enc.supplement = (Supplement(1, 2, "x"),)
    text = repr(enc)
    assert text.startswith("Format1Encoding[nRanges=2,")
    assert "supplement=" in text


def test_populate_from_ranges_via_add() -> None:
    # Simulate the parser-style fill for two ranges:
    #   range 0 -> first=10, n_left=2 (codes 10..12) starting at SID 1
    #   range 1 -> first=50, n_left=0 (only code 50)        SID 2
    enc = Format1Encoding(n_ranges=2)
    enc.add(0, 0, ".notdef")
    enc.add(10, 1)  # SID 1 -> "space"
    enc.add(11, 2)  # SID 2 -> "exclam"
    enc.add(12, 3)  # SID 3 -> "quotedbl"
    enc.add(50, 4)  # SID 4 -> "numbersign"
    assert enc.get_name(10) == "space"
    assert enc.get_name(11) == "exclam"
    assert enc.get_name(12) == "quotedbl"
    assert enc.get_name(50) == "numbersign"


def test_to_string_matches_upstream_format() -> None:
    # Upstream toString (CFFParser.java:1501-1505):
    # ``getClass().getName() + "[nRanges=" + nRanges
    #   + ", supplement=" + Arrays.toString(super.supplement) + "]"``.
    enc = Format1Encoding(4)
    rendered = enc.to_string()
    assert "Format1Encoding" in rendered
    assert "[nRanges=4," in rendered
    assert "supplement=[]" in rendered


def test_to_string_includes_supplement_entries() -> None:
    enc = Format1Encoding(2)
    enc.supplement = (Supplement(1, 2, "x"),)
    rendered = enc.to_string()
    assert "[nRanges=2," in rendered
    assert "supplement=[" in rendered
    assert "]]" in rendered
