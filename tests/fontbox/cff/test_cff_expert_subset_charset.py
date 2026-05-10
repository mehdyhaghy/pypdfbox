"""Hand-written tests for :class:`CFFExpertSubsetCharset`."""

from __future__ import annotations

from pypdfbox.fontbox.cff import CFFExpertSubsetCharset


def test_singleton_identity() -> None:
    assert (
        CFFExpertSubsetCharset.get_instance()
        is CFFExpertSubsetCharset.get_instance()
    )


def test_known_entries() -> None:
    charset = CFFExpertSubsetCharset.get_instance()
    # Spot-check entries from CFFExpertSubsetCharset.java (lines 34-121).
    assert charset.get_name_for_gid(0) == ".notdef"
    assert charset.get_name_for_gid(1) == "space"
    # GID 2 -> SID 231 / "dollaroldstyle".
    assert charset.get_name_for_gid(2) == "dollaroldstyle"
    assert charset.get_sid_for_gid(2) == 231
    # "fraction" appears in upstream table with SID 99.
    assert charset.get_sid("fraction") == 99


def test_table_size() -> None:
    charset = CFFExpertSubsetCharset.get_instance()
    # 87 entries.
    assert charset.get_name_for_gid(86) is not None
    assert charset.get_name_for_gid(87) is None


def test_is_not_cid_font() -> None:
    assert CFFExpertSubsetCharset.get_instance().is_cid_font() is False
