"""Upstream-shaped tests for ``LookupTable``.

There is no standalone ``LookupTableTest`` upstream — the table is
exercised through ``LookupListTableTest`` /
``GlyphSubstitutionTableTest``. These tests capture the constructor /
accessor / ``toString`` invariants of
``org.apache.fontbox.ttf.table.common.LookupTable``.

Upstream Java reference:
- fontbox/src/main/java/org/apache/fontbox/ttf/table/common/LookupTable.java
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import LookupTable


def test_to_string_mirrors_java_format() -> None:
    # Java: String.format(
    #   "LookupTable[lookupType=%d,lookupFlag=%d,markFilteringSet=%d]",
    #   lookupType, lookupFlag, markFilteringSet);
    lt = LookupTable(lookup_type=4, lookup_flag=0x0010, mark_filtering_set=2)
    assert (
        lt.to_string()
        == "LookupTable[lookupType=4,lookupFlag=16,markFilteringSet=2]"
    )
    assert str(lt) == lt.to_string()


def test_to_string_default_construction_zero_fields() -> None:
    assert (
        LookupTable().to_string()
        == "LookupTable[lookupType=0,lookupFlag=0,markFilteringSet=0]"
    )
