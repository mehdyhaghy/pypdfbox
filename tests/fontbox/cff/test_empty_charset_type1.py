"""Hand-written tests for :class:`EmptyCharsetType1`."""

from __future__ import annotations

from pypdfbox.fontbox.cff import CFFCharsetType1, EmptyCharsetType1


def test_only_notdef_registered() -> None:
    charset = EmptyCharsetType1()
    assert charset.is_cid_font() is False
    assert isinstance(charset, CFFCharsetType1)
    assert charset.get_name_for_gid(0) == ".notdef"
    assert charset.get_sid_for_gid(0) == 0
    assert charset.get_gid_for_sid(0) == 0
    assert charset.get_sid(".notdef") == 0
    # Anything past .notdef is absent.
    assert charset.get_name_for_gid(1) is None


def test_str_reports_class_name() -> None:
    charset = EmptyCharsetType1()
    rendered = str(charset)
    assert "EmptyCharsetType1" in rendered


def test_to_string_matches_str() -> None:
    # Upstream toString (CFFParser.java:1541-1545) — getClass().getName().
    charset = EmptyCharsetType1()
    assert charset.to_string() == str(charset)
    assert charset.to_string().endswith("EmptyCharsetType1")
