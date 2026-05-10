"""Hand-written tests for :class:`Format2Charset`."""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.cff import EmbeddedCharset, Format2Charset, RangeMapping


def test_inherits_embedded_charset() -> None:
    charset = Format2Charset(is_cid_font=True)
    assert isinstance(charset, EmbeddedCharset)


def test_range_lookup_runs_unconditionally_for_cid_font() -> None:
    charset = Format2Charset(is_cid_font=True)
    # 16-bit n_left so a single range can span thousands of glyphs.
    charset.add_range_mapping(RangeMapping(start_gid=0, first=0, n_left=4096))

    assert charset.get_cid_for_gid(0) == 0
    assert charset.get_cid_for_gid(2048) == 2048
    assert charset.get_cid_for_gid(4096) == 4096
    assert charset.get_cid_for_gid(4097) == 0  # outside range, base returns 0

    assert charset.get_gid_for_cid(2048) == 2048


def test_format2_walks_ranges_even_when_not_cid_font() -> None:
    # Upstream Format2Charset overrides do not gate on isCIDFont(), unlike
    # Format1Charset. The range list is consulted unconditionally.
    charset = Format2Charset(is_cid_font=False)
    charset.add_range_mapping(RangeMapping(start_gid=1, first=100, n_left=2))

    assert charset.get_cid_for_gid(1) == 100
    assert charset.get_cid_for_gid(3) == 102
    assert charset.get_gid_for_cid(101) == 2

    # Out-of-range falls back to the Type1 base, which raises.
    with pytest.raises(RuntimeError):
        charset.get_cid_for_gid(999)
    with pytest.raises(RuntimeError):
        charset.get_gid_for_cid(999)


def test_multiple_ranges_first_match_wins() -> None:
    charset = Format2Charset(is_cid_font=True)
    charset.add_range_mapping(RangeMapping(start_gid=0, first=10, n_left=4))
    charset.add_range_mapping(RangeMapping(start_gid=5, first=20, n_left=4))

    assert charset.get_cid_for_gid(0) == 10
    assert charset.get_cid_for_gid(4) == 14
    assert charset.get_cid_for_gid(5) == 20
    assert charset.get_cid_for_gid(9) == 24
