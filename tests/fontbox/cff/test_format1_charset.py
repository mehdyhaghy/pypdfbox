"""Hand-written tests for :class:`Format1Charset`."""

from __future__ import annotations

from pypdfbox.fontbox.cff import EmbeddedCharset, Format1Charset, RangeMapping


def test_inherits_embedded_charset() -> None:
    charset = Format1Charset(is_cid_font=True)
    assert isinstance(charset, EmbeddedCharset)


def test_cid_font_uses_range_lookup() -> None:
    charset = Format1Charset(is_cid_font=True)
    # GIDs 1..3 -> CIDs 100..102 (n_left == 2, so 3 glyphs in range).
    charset.add_range_mapping(RangeMapping(start_gid=1, first=100, n_left=2))
    # GIDs 10..11 -> CIDs 200..201.
    charset.add_range_mapping(RangeMapping(start_gid=10, first=200, n_left=1))

    assert charset.get_cid_for_gid(1) == 100
    assert charset.get_cid_for_gid(3) == 102
    assert charset.get_cid_for_gid(10) == 200
    assert charset.get_cid_for_gid(11) == 201
    # Outside any range falls through to base CID storage (empty -> 0).
    assert charset.get_cid_for_gid(99) == 0

    assert charset.get_gid_for_cid(100) == 1
    assert charset.get_gid_for_cid(102) == 3
    assert charset.get_gid_for_cid(201) == 11
    assert charset.get_gid_for_cid(999) == 0


def test_type1_font_skips_range_walk_for_cid_lookups() -> None:
    # When ``is_cid_font`` is False, Format1Charset must not consult the
    # range list — it should defer to the Type1-keyed base which raises.
    charset = Format1Charset(is_cid_font=False)
    charset.add_range_mapping(RangeMapping(start_gid=1, first=100, n_left=2))

    import pytest

    with pytest.raises(RuntimeError):
        charset.get_cid_for_gid(1)
    with pytest.raises(RuntimeError):
        charset.get_gid_for_cid(100)


def test_type1_font_supports_sid_api() -> None:
    charset = Format1Charset(is_cid_font=False)
    charset.add_sid(2, 50, "A")
    assert charset.get_name_for_gid(2) == "A"
    assert charset.get_sid_for_gid(2) == 50
    assert charset.get_gid_for_sid(50) == 2
