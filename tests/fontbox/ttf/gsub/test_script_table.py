from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub import LangSysTable, ScriptTable


def test_default_construction() -> None:
    st = ScriptTable()
    assert st.get_default_lang_sys_table() is None
    assert st.get_lang_sys_tables() == {}


def test_default_lang_sys_round_trip() -> None:
    default = LangSysTable(feature_indices=(0,))
    st = ScriptTable(default_lang_sys_table=default)
    assert st.get_default_lang_sys_table() is default
    assert st.get_lang_sys_tables() == {}


def test_per_language_lang_sys_round_trip() -> None:
    eng = LangSysTable(feature_indices=(1, 2))
    deu = LangSysTable(feature_indices=(3,))
    st = ScriptTable(lang_sys_tables={"ENG ": eng, "DEU ": deu})
    assert st.get_lang_sys_tables()["ENG "] is eng
    assert st.get_lang_sys_tables()["DEU "] is deu
    assert st.get_default_lang_sys_table() is None


def test_to_string_no_default_zero_records() -> None:
    # Mirrors upstream ``ScriptTable[hasDefault=false,langSysRecordsCount=0]``.
    st = ScriptTable()
    assert st.to_string() == "ScriptTable[hasDefault=false,langSysRecordsCount=0]"
    assert str(st) == st.to_string()


def test_to_string_with_default_and_lang_sys_records() -> None:
    default = LangSysTable(feature_indices=(0,))
    eng = LangSysTable(feature_indices=(1,))
    deu = LangSysTable(feature_indices=(2,))
    st = ScriptTable(
        default_lang_sys_table=default,
        lang_sys_tables={"ENG ": eng, "DEU ": deu},
    )
    assert (
        st.to_string()
        == "ScriptTable[hasDefault=true,langSysRecordsCount=2]"
    )
