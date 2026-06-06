"""Wave 1495 — behaviour-anchored coverage for ``OTFParser.read_table``'s
tag dispatch (OTL tags -> ``OTLTable``, ``CFF `` -> ``CFFTable``, everything
else -> the inherited ``TTFParser.read_table``) plus the public factory hooks
(``new_font`` / ``allow_cff``) and their leading-underscore legacy forwards.

Mirrors ``org.apache.fontbox.ttf.OTFParser`` (read_table switch L66-L82,
newFont L60-L63, allowCFF L85-L88).
"""

from __future__ import annotations

import pytest

from pypdfbox.fontbox.ttf.cff_table import CFFTable
from pypdfbox.fontbox.ttf.otf_parser import OTFParser
from pypdfbox.fontbox.ttf.otl_table import OTLTable
from pypdfbox.fontbox.ttf.ttf_table import TTFTable


@pytest.mark.parametrize("tag", ["BASE", "GDEF", "GPOS", "GSUB", "JSTF"])
def test_read_table_routes_otl_tags_to_otl_table(tag: str) -> None:
    table = OTFParser().read_table(tag)
    assert isinstance(table, OTLTable)
    assert table.get_tag() == tag


def test_read_table_routes_cff_tag_to_cff_table() -> None:
    table = OTFParser().read_table("CFF ")
    assert isinstance(table, CFFTable)
    assert table.get_tag() == "CFF "


def test_read_table_falls_through_to_super_for_other_tags() -> None:
    # ``head`` is not an OTL/CFF tag, so it takes the inherited path and comes
    # back as a plain base ``TTFTable`` (the base factory doesn't set a tag).
    table = OTFParser().read_table("head")
    assert type(table) is TTFTable
    assert not isinstance(table, (OTLTable, CFFTable))


def test_allow_cff_is_true_for_otf() -> None:
    assert OTFParser().allow_cff() is True


def test_legacy_underscore_hooks_forward_to_public_methods() -> None:
    parser = OTFParser()
    # The underscored legacy forwards delegate to the public methods.
    assert parser._allow_cff() is True
    assert isinstance(parser._read_table("CFF "), CFFTable)
    assert isinstance(parser._read_table("GSUB"), OTLTable)
