from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf import CFFTable, OTFParser, OTLTable, TTFTable
from pypdfbox.fontbox.ttf.otf_parser import _OTF_OTL_TAGS


def test_is_ttf_table_subclass() -> None:
    assert issubclass(OTLTable, TTFTable)


def test_tag_constant_is_jstf() -> None:
    assert OTLTable.TAG == "JSTF"


def test_default_tag_empty_until_set() -> None:
    table = OTLTable()
    assert table.get_tag() == ""


def test_set_tag_round_trips() -> None:
    table = OTLTable()
    table.set_tag("GPOS")
    assert table.get_tag() == "GPOS"


@pytest.mark.parametrize("tag", ["BASE", "GDEF", "GPOS", "GSUB", "JSTF"])
def test_read_table_returns_otl_table_for_layout_tags(tag: str) -> None:
    # Mirrors the upstream OTFParser.readTable switch: every OpenType
    # Layout tag (including GSUB, which is a documented stub) resolves to
    # an OTLTable carrying the requested tag.
    parser = OTFParser()
    table = parser.read_table(tag)
    assert isinstance(table, OTLTable)
    assert table.get_tag() == tag


def test_read_table_returns_cff_table_for_cff_tag() -> None:
    parser = OTFParser()
    table = parser.read_table("CFF ")
    assert isinstance(table, CFFTable)
    assert table.get_tag() == "CFF "


def test_read_table_falls_back_for_other_tags() -> None:
    parser = OTFParser()
    table = parser.read_table("name")
    # Unhandled tags defer to the base TTFParser, which yields a generic
    # TTFTable (the read_table factory hook), never an OTLTable/CFFTable.
    assert type(table) is TTFTable


def test_otl_tags_cover_expected_layout_set() -> None:
    assert set(_OTF_OTL_TAGS) == {"BASE", "GDEF", "GPOS", "GSUB", "JSTF"}
