"""Upstream-style port of ``GlyphSubstitutionTableTest`` from PDFBox 3.0
(``fontbox/src/test/java/org/apache/fontbox/ttf/GlyphSubstitutionTableTest.java``).

The upstream test ``testGetGsubData`` loads ``Lohit-Bengali.ttf`` and
asserts the structure of a ported ``GsubData`` value class — including
``Language.BENGALI``, the active script ``bng2``, and twelve feature
tags (``abvs``, ``akhn``, ``blwf``, ``blws``, ``half``, ``haln``,
``init``, ``nukt``, ``pres``, ``pstf``, ``rphf``, ``vatu``).

We intentionally do **not** port that assertion shape: pypdfbox does
not port the ``org.apache.fontbox.ttf.model.{GsubData, Language,
ScriptFeature, MapBackedScriptFeature}`` value-class graph (see
``CHANGES.md``). The ``Lohit-Bengali.ttf`` fixture and the per-feature
``/gsub/lohit_bengali/bng2/<feature>.txt`` golden tables are also not
copied into ``tests/fixtures``.

Instead this file ports the *intent* of the upstream test against the
``LiberationSans-Regular.ttf`` fixture we already ship: load a font
with GSUB, read it, and confirm the public surface
(``get_supported_script_tags`` + ``get_supported_feature_tags``)
returns the expected inventory.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import GlyphSubstitutionTable, TrueTypeFont

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
    # Wave 1375: ``get_gsub_data()`` now projects a real :class:`GsubData`
    # view (see ``GlyphSubstitutionTable.get_gsub_data`` docstring). The
    # default invocation resolves to the most-preferred supported script.
    gsub_data = table.get_gsub_data()
    assert gsub_data is not None
    assert gsub_data.get_active_script_name() == "latn"
