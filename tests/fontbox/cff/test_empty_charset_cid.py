"""Hand-written tests for :class:`EmptyCharsetCID`."""

from __future__ import annotations

from pypdfbox.fontbox.cff import CFFCharsetCID, EmptyCharsetCID


def test_identity_mapping_populated() -> None:
    charset = EmptyCharsetCID(num_char_strings=5)
    assert charset.is_cid_font() is True
    assert isinstance(charset, CFFCharsetCID)

    # Identity for 0..5 inclusive (upstream: i in [1, num_char_strings]
    # plus the explicit (0, 0) entry).
    for i in range(6):
        assert charset.get_gid_for_cid(i) == i
        assert charset.get_cid_for_gid(i) == i


def test_zero_char_strings_only_notdef() -> None:
    charset = EmptyCharsetCID(num_char_strings=0)
    assert charset.get_gid_for_cid(0) == 0
    assert charset.get_cid_for_gid(0) == 0
    # Anything past 0 is unmapped.
    assert charset.get_gid_for_cid(1) == 0


def test_str_reports_class_name() -> None:
    charset = EmptyCharsetCID(num_char_strings=2)
    rendered = str(charset)
    assert "EmptyCharsetCID" in rendered


def test_to_string_matches_str() -> None:
    # Upstream toString (CFFParser.java:1524-1528) — getClass().getName().
    charset = EmptyCharsetCID(num_char_strings=2)
    assert charset.to_string() == str(charset)
    assert charset.to_string().endswith("EmptyCharsetCID")
