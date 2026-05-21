"""Port of upstream ``GlyphSubstitutionTableLiberationFontTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/GlyphSubstitutionTableLiberationFontTest.java``.

All five upstream cases run end-to-end against the bundled
``LiberationSans-Regular.ttf`` fixture once wave 1375 added the
:meth:`GlyphSubstitutionTable.get_gsub_data` projection — see the
``GsubData`` deviation note in
:class:`pypdfbox.fontbox.ttf.GlyphSubstitutionTable`.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pypdfbox.fontbox.ttf import OTFParser
from pypdfbox.fontbox.ttf.model.language import Language

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pypdfbox.fontbox.ttf import OpenTypeFont

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


@pytest.fixture
def font() -> Iterator[OpenTypeFont]:
    if not FIXTURE.exists():
        pytest.skip(f"Fixture font not present: {FIXTURE}")
    parser = OTFParser()
    parsed = parser.parse(FIXTURE.read_bytes())
    try:
        yield parsed
    finally:
        parsed.close()


# Translated from getGsubDataDefault.
def test_get_gsub_data_default(font: OpenTypeFont) -> None:
    gsub_data = font.get_gsub_data()
    assert gsub_data.get_active_script_name() == "latn"


# Translated from getGsubDataForUnsupportedScriptTag.
def test_get_gsub_data_for_unsupported_script_tag(font: OpenTypeFont) -> None:
    gsub = font.get_gsub()
    assert gsub is not None
    gsub_data = gsub.get_gsub_data("<some_non_existent_script_tag>")
    assert gsub_data is None


# Translated from testGetGsubDataForCyrillic.
def test_get_gsub_data_for_cyrillic(font: OpenTypeFont) -> None:
    gsub = font.get_gsub()
    assert gsub is not None
    cyrillic_script_tag = "cyrl"
    expected_features = {"subs", "sups"}

    cyrillic_gsub_data = gsub.get_gsub_data(cyrillic_script_tag)

    assert cyrillic_gsub_data is not None
    assert cyrillic_gsub_data.get_active_script_name() == cyrillic_script_tag
    assert cyrillic_gsub_data.get_supported_features() == expected_features


# Translated from getSupportedScriptTags.
def test_get_supported_script_tags(font: OpenTypeFont) -> None:
    gsub = font.get_gsub()
    assert gsub is not None
    expected = {"DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"}
    assert gsub.get_supported_script_tags() == expected


# Translated from checkGsubDataLoadingForAllSupportedScripts (the
# JUnit ``@ParameterizedTest`` with ``@ValueSource``).
@pytest.mark.parametrize(
    "script_tag", ["DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"]
)
def test_check_gsub_data_loading_for_all_supported_scripts(
    font: OpenTypeFont, script_tag: str
) -> None:
    from pypdfbox.fontbox.ttf.gsub.gsub_data import GsubData

    gsub = font.get_gsub()
    assert gsub is not None
    gsub_data = gsub.get_gsub_data(script_tag)
    assert gsub_data is not None
    assert gsub_data is not GsubData.NO_DATA_FOUND
    assert gsub_data.get_language() == Language.UNSPECIFIED.name
    assert gsub_data.get_active_script_name() == script_tag
