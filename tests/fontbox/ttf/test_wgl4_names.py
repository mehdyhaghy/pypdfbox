from __future__ import annotations

from pypdfbox.fontbox.ttf.wgl4_names import (
    NUMBER_OF_MAC_GLYPHS,
    get_all_names,
    get_glyph_index,
    get_glyph_name,
)


def test_number_of_mac_glyphs_constant() -> None:
    assert NUMBER_OF_MAC_GLYPHS == 258


def test_get_all_names_returns_full_list() -> None:
    names = get_all_names()
    assert len(names) == NUMBER_OF_MAC_GLYPHS
    assert names[0] == ".notdef"
    assert names[1] == ".null"
    assert names[3] == "space"
    assert names[-1] == "dcroat"


def test_get_all_names_returns_fresh_copy() -> None:
    a = get_all_names()
    b = get_all_names()
    assert a == b
    assert a is not b
    a[0] = "MUTATED"
    # second call is unaffected by mutation of first
    assert get_all_names()[0] == ".notdef"


def test_get_glyph_name_first_and_last() -> None:
    assert get_glyph_name(0) == ".notdef"
    assert get_glyph_name(NUMBER_OF_MAC_GLYPHS - 1) == "dcroat"


def test_get_glyph_name_middle_samples() -> None:
    assert get_glyph_name(3) == "space"
    assert get_glyph_name(36) == "A"
    assert get_glyph_name(257) == "dcroat"


def test_get_glyph_name_out_of_range_returns_none() -> None:
    assert get_glyph_name(-1) is None
    assert get_glyph_name(NUMBER_OF_MAC_GLYPHS) is None
    assert get_glyph_name(10000) is None


def test_get_glyph_index_known_names() -> None:
    assert get_glyph_index(".notdef") == 0
    assert get_glyph_index("space") == 3
    assert get_glyph_index("A") == 36
    assert get_glyph_index("dcroat") == 257


def test_get_glyph_index_unknown_returns_none() -> None:
    assert get_glyph_index("definitely_not_a_glyph") is None
    assert get_glyph_index("") is None


def test_round_trip_index_to_name_to_index() -> None:
    for i in range(NUMBER_OF_MAC_GLYPHS):
        name = get_glyph_name(i)
        assert name is not None
        assert get_glyph_index(name) == i


def test_all_names_are_unique() -> None:
    names = get_all_names()
    assert len(set(names)) == len(names)
