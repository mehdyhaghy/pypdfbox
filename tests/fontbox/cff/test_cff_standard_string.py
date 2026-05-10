"""Hand-written tests for
:class:`pypdfbox.fontbox.cff.cff_standard_string.CFFStandardString`.

Boundary-focused: SID 0 (.notdef), SID 1 (space), SID 390 (Semibold,
last Standard SID per Adobe Technote #5176), and SID 391+ which is
defined to live in the per-font STRING INDEX — :meth:`get_name` returns
``None`` there so callers can fall through to the font-private table
(matches upstream ``CFFParser.readString`` flow,
``CFFParser.java`` lines 909-925).
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff.cff_standard_string import (
    NUM_STANDARD_STRINGS,
    CFFStandardString,
)


def test_constant_count_is_391() -> None:
    assert NUM_STANDARD_STRINGS == 391


def test_get_name_sid_zero_is_notdef() -> None:
    assert CFFStandardString.get_name(0) == ".notdef"


def test_get_name_sid_one_is_space() -> None:
    assert CFFStandardString.get_name(1) == "space"


def test_get_name_sid_390_is_last_standard_string() -> None:
    # Last entry in upstream's ``SID2STR`` array (line 432) is "Semibold".
    assert CFFStandardString.get_name(390) == "Semibold"


def test_get_name_sid_391_is_none() -> None:
    # SID 391 falls outside the Standard Strings table — caller is
    # expected to look it up in the font's per-font STRING INDEX.
    assert CFFStandardString.get_name(391) is None


def test_get_name_negative_sid_is_none() -> None:
    assert CFFStandardString.get_name(-1) is None


def test_get_name_far_out_of_range_is_none() -> None:
    assert CFFStandardString.get_name(10_000) is None


def test_class_is_static_only() -> None:
    # Upstream constructor is private; we reject instantiation outright.
    with pytest.raises(TypeError):
        CFFStandardString()


def test_get_name_some_well_known_sids() -> None:
    # Spot-check a handful of well-known SIDs from the CFF spec.
    assert CFFStandardString.get_name(2) == "exclam"
    assert CFFStandardString.get_name(34) == "A"
    assert CFFStandardString.get_name(66) == "a"
