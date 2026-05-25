"""Wave 1403 — branch round-out for
:class:`GlyphSubstitutionDataExtractor`.

Closes the partial arc ``[116,123]`` — the ``default_lang_sys_table is
not None`` False branch in :meth:`build_map_backed_gsub_data`: a script
table that declares *only* language-specific LangSys records (no default
LangSys) skips the default-table population and falls through to the
per-language loop.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.gsub.glyph_substitution_data_extractor import (
    GlyphSubstitutionDataExtractor,
)
from pypdfbox.fontbox.ttf.gsub.lang_sys_table import LangSysTable
from pypdfbox.fontbox.ttf.gsub.script_table import ScriptTable


def test_build_map_backed_gsub_data_no_default_lang_sys() -> None:
    """A ScriptTable with no default LangSys but a language-specific one
    skips the default-population block and processes the per-language
    LangSys instead ([116,123] False arc).

    The language-specific LangSys references feature index 0, but the
    feature list is empty (no record at index 0), so the per-feature
    population is a no-op — what we exercise is the *branch*, not the
    feature extraction.
    """
    extractor = GlyphSubstitutionDataExtractor()
    script_table = ScriptTable(
        default_lang_sys_table=None,
        lang_sys_tables={"ENG ": LangSysTable(feature_indices=(0,))},
    )
    result = extractor.get_gsub_data_for_script(
        "latn",
        script_table,
        feature_list_table_records=(),
        lookup_list_tables=(),
    )
    assert result is not None
    # No default LangSys, empty feature list -> empty substitution map.
    assert result.get_active_script_name() == "latn"
    assert result.get_supported_features() == set()
