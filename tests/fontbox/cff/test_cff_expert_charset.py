"""Hand-written tests for :class:`CFFExpertCharset`."""

from __future__ import annotations

from pypdfbox.fontbox.cff import CFFExpertCharset


def test_singleton_identity() -> None:
    assert CFFExpertCharset.get_instance() is CFFExpertCharset.get_instance()


def test_known_entries() -> None:
    charset = CFFExpertCharset.get_instance()
    # Spot-check entries from CFFExpertCharset.java (lines 33-198).
    # GID 0/1 are .notdef/space (SIDs 0/1).
    assert charset.get_name_for_gid(0) == ".notdef"
    assert charset.get_sid_for_gid(0) == 0
    assert charset.get_name_for_gid(1) == "space"
    assert charset.get_sid_for_gid(1) == 1
    # GID 2 -> SID 229 / "exclamsmall".
    assert charset.get_name_for_gid(2) == "exclamsmall"
    assert charset.get_sid_for_gid(2) == 229
    # "comma" sits at GID 12 with SID 13 in the upstream table.
    assert charset.get_name_for_gid(12) == "comma"
    assert charset.get_sid_for_gid(12) == 13
    # Reverse name -> SID lookup.
    assert charset.get_sid("Hungarumlautsmall") == 230


def test_table_size() -> None:
    charset = CFFExpertCharset.get_instance()
    # 166 entries: GID 0..165.
    assert charset.get_name_for_gid(165) is not None
    assert charset.get_name_for_gid(166) is None


def test_is_not_cid_font() -> None:
    assert CFFExpertCharset.get_instance().is_cid_font() is False
