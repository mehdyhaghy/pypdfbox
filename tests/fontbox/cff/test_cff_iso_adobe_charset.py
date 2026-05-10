"""Hand-written tests for :class:`CFFISOAdobeCharset`."""

from __future__ import annotations

from pypdfbox.fontbox.cff import CFFISOAdobeCharset


def test_singleton_identity() -> None:
    assert CFFISOAdobeCharset.get_instance() is CFFISOAdobeCharset.get_instance()


def test_known_glyph_lookups() -> None:
    charset = CFFISOAdobeCharset.get_instance()
    # ISOAdobe is a predefined charset where SID == GID for the first 229
    # glyphs; verify a few representative entries from the upstream Java
    # table (see CFFISOAdobeCharset.java lines 33-263).
    assert charset.get_name_for_gid(0) == ".notdef"
    assert charset.get_name_for_gid(1) == "space"
    assert charset.get_name_for_gid(34) == "A"
    assert charset.get_name_for_gid(228) == "zcaron"
    assert charset.get_sid_for_gid(34) == 34
    assert charset.get_gid_for_sid(34) == 34
    assert charset.get_sid("A") == 34


def test_table_size() -> None:
    charset = CFFISOAdobeCharset.get_instance()
    # 229 entries (GID 0..228) per upstream table.
    assert charset.get_name_for_gid(228) is not None
    assert charset.get_name_for_gid(229) is None


def test_is_not_cid_font() -> None:
    assert CFFISOAdobeCharset.get_instance().is_cid_font() is False
