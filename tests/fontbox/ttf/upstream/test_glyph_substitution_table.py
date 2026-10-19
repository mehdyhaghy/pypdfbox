"""Upstream-style port of ``GlyphSubstitutionTableTest`` from PDFBox 3.0
(``fontbox/src/test/java/org/apache/fontbox/ttf/GlyphSubstitutionTableTest.java``).

The upstream test ``testGetGsubData`` loads ``Lohit-Bengali.ttf`` and
asserts the structure of a ported ``GsubData`` value class — including
``Language.BENGALI``, the active script ``bng2``, and twelve feature
tags (``abvs``, ``akhn``, ``blwf``, ``blws``, ``half``, ``haln``,
``init``, ``nukt``, ``pres``, ``pstf``, ``rphf``, ``vatu``).

The ``Lohit-Bengali.ttf`` fixture (SIL OFL) and the per-feature
``/gsub/lohit_bengali/bng2/<feature>.txt`` golden tables are not
copied into ``tests/fixtures`` (wave 1360 rule), so the Bengali
assertions cannot run.

Instead this file ports the *intent* of the upstream test against the
``LiberationSans-Regular.ttf`` fixture we already ship: load a font
with GSUB, read it, and confirm the public surface
(``get_supported_script_tags`` + ``get_supported_feature_tags``)
returns the expected inventory.
"""

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import GlyphSubstitutionTable, TrueTypeFont
from pypdfbox.fontbox.ttf.model.language import Language

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

# LiberationSans's GSUB carries: ccmp dlig subs sups (with ccmp twice —
# one for Latin/Greek/etc., one for Hebrew). Our populate-time dedup
# keeps the first occurrence, so the unique feature set is four tags.
EXPECTED_FEATURES = {"ccmp", "dlig", "subs", "sups"}
EXPECTED_SCRIPTS = {"DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"}


def test_get_gsub_data() -> None:
    """``testGetGsubData`` — ported via spirit, not letter (see module
    docstring). Confirms a real GSUB table is decoded with the expected
    script + feature inventory."""
    if not FIXTURE.exists():
        pytest.skip("Fixture font not present (LiberationSans-Regular.ttf)")
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())

    table = ttf.get_gsub()

    assert table is not None
    assert isinstance(table, GlyphSubstitutionTable)
    assert table.get_initialized() is True
    assert table.get_supported_script_tags() == EXPECTED_SCRIPTS
    assert set(table.get_supported_feature_tags()) == EXPECTED_FEATURES
    # The default invocation resolves the first supported Language.
    gsub_data = table.get_gsub_data()
    assert gsub_data is not None
    assert gsub_data.get_language() is Language.LATIN
    assert gsub_data.get_active_script_name() == "latn"
    assert gsub_data.get_supported_features() == {"ccmp", "subs", "sups"}
