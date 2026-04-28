"""Upstream-style port for ``GlyphPositioningTable``.

PDFBox 3.0 does not ship a dedicated ``GlyphPositioningTableTest`` —
the upstream class is itself a thin scaffold (``TAG`` constant only,
no parsing). The closest upstream coverage lives in the GPOS-aware
behaviour exercised by the kerning + text-rendering pipelines, which
we already cover under the GSUB upstream port and the kerning-table
tests.

To keep this module aligned with the GSUB-side upstream-port shape,
we exercise the public structural surface against the bundled
``LiberationSans-Regular.ttf`` fixture: load the font, read the GPOS
table, confirm the script / feature inventory and the lookup-list
breadth match the on-disk structure.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pypdfbox.fontbox.ttf import GlyphPositioningTable, TrueTypeFont

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)

# LiberationSans's GPOS carries: kern (latin + hebrew), mark, mkmk.
# Populate-time dedup keeps the first occurrence so the unique tag
# inventory is three feature tags.
EXPECTED_FEATURES_AT_LEAST = {"kern", "mark", "mkmk"}
EXPECTED_SCRIPTS = {"DFLT", "bopo", "copt", "cyrl", "grek", "hebr", "latn"}


def test_get_gpos_data() -> None:
    """Spirit-port of the upstream GSUB ``testGetGsubData`` shape, applied
    to GPOS — confirms a real GPOS table is decoded with the expected
    script + feature inventory."""
    if not FIXTURE.exists():
        pytest.skip("Fixture font not present (LiberationSans-Regular.ttf)")
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())

    table = ttf.get_gpos()

    assert table is not None
    assert isinstance(table, GlyphPositioningTable)
    assert table.get_initialized() is True
    assert table.get_supported_script_tags() == EXPECTED_SCRIPTS
    assert set(table.get_supported_feature_tags()) >= EXPECTED_FEATURES_AT_LEAST


def test_gpos_lookup_list_breadth() -> None:
    """The fixture font advertises lookups across types 1, 2, 4, 6, 8.
    Confirm the structural accessors expose the same."""
    if not FIXTURE.exists():
        pytest.skip("Fixture font not present (LiberationSans-Regular.ttf)")
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())

    table = ttf.get_gpos()
    assert table is not None
    types = set(table.get_lookup_types())
    assert {1, 2, 4, 6, 8} <= types


def test_gpos_kern_feature_lookup_indices_are_pair_adjustment() -> None:
    """Every lookup the ``kern`` feature points at must be type-2
    (pair adjustment) — anything else would be a broken font / broken
    inventory walk."""
    if not FIXTURE.exists():
        pytest.skip("Fixture font not present (LiberationSans-Regular.ttf)")
    ttf = TrueTypeFont.from_bytes(FIXTURE.read_bytes())

    table = ttf.get_gpos()
    assert table is not None
    types = table.get_lookup_types()
    for li in table.get_lookup_indices_for_feature("kern"):
        assert types[li] == GlyphPositioningTable.LOOKUP_TYPE_PAIR_ADJUSTMENT
