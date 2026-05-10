"""Hand-written tests for the abstract :class:`CFFEncoding` base class."""

from __future__ import annotations

from pypdfbox.fontbox.cff.cff_encoding import CFFEncoding


class _Probe(CFFEncoding):
    """Subclass used to exercise the abstract base; doesn't auto-populate."""


def test_add_three_arg_uses_explicit_name() -> None:
    enc = _Probe()
    enc.add(65, 34, "A")
    assert enc.get_name(65) == "A"
    assert enc.get_code("A") == 65


def test_add_two_arg_resolves_sid_via_standard_strings() -> None:
    # SID 1 -> "space" in the CFF standard strings table.
    enc = _Probe()
    enc.add(32, 1)
    assert enc.get_name(32) == "space"
    assert enc.get_code("space") == 32


def test_add_two_arg_sid_zero_is_notdef() -> None:
    enc = _Probe()
    enc.add(127, 0)
    assert enc.get_name(127) == ".notdef"


def test_add_out_of_range_sid_falls_back_to_notdef() -> None:
    enc = _Probe()
    enc.add(200, 99_999)  # past end of cffStandardStrings
    assert enc.get_name(200) == ".notdef"


def test_unmapped_code_returns_notdef() -> None:
    enc = _Probe()
    assert enc.get_name(7) == ".notdef"


def test_inherits_encoding_get_codes_snapshot() -> None:
    enc = _Probe()
    enc.add(1, 0, "x")
    snapshot = enc.get_code_to_name_map()
    assert snapshot == {1: "x"}
    snapshot[2] = "y"
    # Mutation of snapshot must not leak back into the encoding.
    assert enc.get_code_to_name_map() == {1: "x"}
