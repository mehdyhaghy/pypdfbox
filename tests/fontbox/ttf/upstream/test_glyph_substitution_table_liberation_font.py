"""Port of upstream ``GlyphSubstitutionTableLiberationFontTest`` from
``fontbox/src/test/java/org/apache/fontbox/ttf/GlyphSubstitutionTableLiberationFontTest.java``.

Two cases run end-to-end against the bundled
``LiberationSans-Regular.ttf`` fixture (the same TTF used by
``tests/fontbox/ttf/test_glyph_substitution_table.py``):

- ``getSupportedScriptTags`` exercises
  :meth:`GlyphSubstitutionTable.get_supported_script_tags`, which is
  fully ported.
- ``checkGsubDataLoadingForAllSupportedScripts`` (the parametrized
  case) is skipped because it depends on the
  ``GsubData`` value-class projection that pypdfbox does not port —
  see the class docstring of
  :class:`pypdfbox.fontbox.ttf.GlyphSubstitutionTable`. The same
  caveat applies to ``getGsubDataDefault`` and
  ``testGetGsubDataForCyrillic``.

- ``getGsubDataForUnsupportedScriptTag`` collapses to the trivial
  ``get_gsub_data(scriptTag) is None`` invariant on pypdfbox (the
  method always returns ``None``); we still port it so the upstream
  contract is pinned at API level.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from pypdfbox.fontbox.ttf import OTFParser

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


# Translated from getGsubDataDefault -- skipped because pypdfbox does
# not project the upstream ``GsubData`` value class (see
# ``GlyphSubstitutionTable`` class docstring; ``get_gsub_data`` always
# returns ``None`` by design).
def test_get_gsub_data_default(font: OpenTypeFont) -> None:
    pytest.skip(
        "pypdfbox does not project the upstream GsubData value class; "
        "get_gsub_data() always returns None — see "
        "pypdfbox.fontbox.ttf.GlyphSubstitutionTable class docstring."
    )


# Translated from getGsubDataForUnsupportedScriptTag -- the upstream
# contract returning ``null`` for an unsupported script tag collapses
# to the broader "``get_gsub_data`` always returns ``None``"
# invariant in pypdfbox. We still pin it so future implementations
# never regress the unsupported-tag case.
def test_get_gsub_data_for_unsupported_script_tag(font: OpenTypeFont) -> None:
    gsub = font.get_gsub()
    assert gsub is not None
    gsub_data = gsub.get_gsub_data("<some_non_existent_script_tag>")
    assert gsub_data is None


# Translated from testGetGsubDataForCyrillic -- skipped (same reason
# as ``test_get_gsub_data_default``).
def test_get_gsub_data_for_cyrillic(font: OpenTypeFont) -> None:
    pytest.skip(
        "pypdfbox does not project the upstream GsubData value class; "
        "see test_get_gsub_data_default for the rationale."
    )


# Translated from getSupportedScriptTags -- this case exercises a
# fully-ported accessor and is the only end-to-end assertion that
# survives the deviation.
def test_get_supported_script_tags(font: OpenTypeFont) -> None:
    gsub = font.get_gsub()
    assert gsub is not None
    expected = {"DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"}
    assert gsub.get_supported_script_tags() == expected


# Translated from checkGsubDataLoadingForAllSupportedScripts (the
# JUnit ``@ParameterizedTest`` with ``@ValueSource``) -- skipped
# because the assertion targets ``getActiveScriptName()`` on a
# ``GsubData`` projection that pypdfbox does not implement.
@pytest.mark.parametrize(
    "script_tag", ["DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"]
)
def test_check_gsub_data_loading_for_all_supported_scripts(
    font: OpenTypeFont, script_tag: str
) -> None:
    pytest.skip(
        "pypdfbox does not project the upstream GsubData value class; "
        "see test_get_gsub_data_default for the rationale."
    )
