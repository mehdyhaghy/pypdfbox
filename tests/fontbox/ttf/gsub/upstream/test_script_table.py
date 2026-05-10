"""Upstream-shaped tests for ``ScriptTable``.

There is no standalone ``ScriptTableTest`` upstream — the table is
exercised through ``ScriptListTableTest`` /
``GlyphSubstitutionTableTest``. These tests capture the constructor /
accessor / ``toString`` invariants of
``org.apache.fontbox.ttf.table.common.ScriptTable``.

Upstream Java reference:
- fontbox/src/main/java/org/apache/fontbox/ttf/table/common/ScriptTable.java
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import LangSysTable, ScriptTable


def test_to_string_no_default_no_records_mirrors_java_format() -> None:
    # Java: String.format("ScriptTable[hasDefault=%s,langSysRecordsCount=%d]",
    #     defaultLangSysTable != null, langSysTables.size());
    st = ScriptTable()
    assert st.to_string() == "ScriptTable[hasDefault=false,langSysRecordsCount=0]"


def test_to_string_with_default_and_records_mirrors_java_format() -> None:
    default = LangSysTable(feature_indices=(0,))
    eng = LangSysTable(feature_indices=(1,))
    st = ScriptTable(
        default_lang_sys_table=default, lang_sys_tables={"ENG ": eng}
    )
    assert (
        st.to_string()
        == "ScriptTable[hasDefault=true,langSysRecordsCount=1]"
    )
    assert str(st) == st.to_string()
