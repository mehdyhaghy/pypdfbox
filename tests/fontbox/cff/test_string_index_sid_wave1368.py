"""Wave 1368 — SID resolution across the standard-string boundary.

CFF spec §10 partitions SIDs into two halves:

* **SID 0 .. 390** — the immutable 391-entry standard-string table.
* **SID 391+** — indexes into the per-font String INDEX (i.e. SID 391
  is the first entry of the parser's ``_string_index`` list).

The parser falls back to ``"SID<n>"`` when a SID lands past the end of
the per-font String INDEX. These tests pin down each branch of that
dispatch.
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_parser import CFFParser
from pypdfbox.fontbox.cff.cff_standard_string import (
    NUM_STANDARD_STRINGS,
    CFFStandardString,
)
from pypdfbox.fontbox.cff.dict_data import DictData, Entry


def test_num_standard_strings_is_391() -> None:
    # Adobe TN5176 §10: exactly 391 standard strings.
    assert NUM_STANDARD_STRINGS == 391


def test_read_string_sid_zero_is_notdef() -> None:
    parser = CFFParser()
    assert parser.read_string(0) == ".notdef"


def test_read_string_sid_one_is_space() -> None:
    parser = CFFParser()
    assert parser.read_string(1) == "space"


def test_read_string_sid_390_is_last_standard_entry() -> None:
    parser = CFFParser()
    # SID 390 is the last standard string — match the fontTools table.
    expected = CFFStandardString.get_name(390)
    assert parser.read_string(390) == expected
    assert expected is not None


def test_read_string_sid_391_uses_first_per_font_string_when_present() -> None:
    parser = CFFParser()
    parser._string_index = ["customFontName"]
    assert parser.read_string(391) == "customFontName"


def test_read_string_sid_392_uses_second_per_font_string_when_present() -> None:
    parser = CFFParser()
    parser._string_index = ["custom1", "custom2", "custom3"]
    assert parser.read_string(391) == "custom1"
    assert parser.read_string(392) == "custom2"
    assert parser.read_string(393) == "custom3"


def test_read_string_falls_back_to_sid_placeholder_past_string_index() -> None:
    parser = CFFParser()
    parser._string_index = ["custom1"]
    # Only one custom string → SID 392 must fall back.
    assert parser.read_string(392) == "SID392"


def test_read_string_falls_back_to_sid_placeholder_when_index_is_none() -> None:
    parser = CFFParser()
    # parser._string_index defaults to None.
    assert parser.read_string(500) == "SID500"


def test_read_string_falls_back_for_empty_string_index() -> None:
    parser = CFFParser()
    parser._string_index = []
    assert parser.read_string(391) == "SID391"


def test_read_string_rejects_negative_sid() -> None:
    parser = CFFParser()
    with pytest.raises(OSError, match="negative index"):
        parser.read_string(-1)
    with pytest.raises(OSError, match="negative index"):
        parser.read_string(-100)


def test_read_string_boundary_390_vs_391() -> None:
    # SID 390 is a standard string regardless of the per-font index.
    # SID 391 leaves the standard table — must consult the per-font
    # index even when that index contains entries.
    parser = CFFParser()
    parser._string_index = ["shadow_390"]
    assert parser.read_string(390) == CFFStandardString.get_name(390)
    # SID 391 hits the per-font index, not the standard table.
    assert parser.read_string(391) == "shadow_390"


def test_get_string_returns_none_when_entry_missing() -> None:
    parser = CFFParser()
    parser._string_index = ["foo"]
    assert parser.get_string(DictData(), "version") is None


def test_get_string_returns_none_when_entry_has_no_operands() -> None:
    parser = CFFParser()
    parser._string_index = ["foo"]
    d = DictData()
    # Entry with no operands but a valid operator_name.
    e = Entry()
    e.operator_name = "version"
    d.add(e)
    assert parser.get_string(d, "version") is None


def test_get_string_resolves_via_read_string_when_present() -> None:
    parser = CFFParser()
    parser._string_index = ["1.0"]
    d = DictData()
    e = Entry()
    e.operator_name = "version"
    e.add_operand(391)  # → "1.0" via per-font string index
    d.add(e)
    assert parser.get_string(d, "version") == "1.0"


def test_get_string_resolves_to_standard_string_for_small_sid() -> None:
    parser = CFFParser()
    d = DictData()
    e = Entry()
    e.operator_name = "FamilyName"
    e.add_operand(7)  # standard SID 7 → "ampersand"
    d.add(e)
    assert parser.get_string(d, "FamilyName") == CFFStandardString.get_name(7)


def test_cff_standard_string_negative_sid_returns_none() -> None:
    assert CFFStandardString.get_name(-1) is None


def test_cff_standard_string_far_out_of_range_returns_none() -> None:
    # Past 390 must be None (the per-font index is the parser's job).
    assert CFFStandardString.get_name(391) is None
    assert CFFStandardString.get_name(999999) is None


def test_cff_standard_string_well_known_sids_match_spec() -> None:
    # A handful of standard names from the CFF spec.
    assert CFFStandardString.get_name(0) == ".notdef"
    assert CFFStandardString.get_name(1) == "space"
    # SID 11 is "asterisk" per the standard table.
    assert CFFStandardString.get_name(11) == "asterisk"
