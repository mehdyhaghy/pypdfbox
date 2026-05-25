"""Wave 1403 — branch round-out for :class:`GlyphPositioningTable`.

Closes the partial arc ``[128,140]`` — the ``self._gpos_table is not
None`` False branch in :meth:`populate_from_fonttools`: when the
fontTools GPOS wrapper exposes no parsed ``.table`` structure, script /
feature tag harvesting is skipped and the tag lists end up empty.
"""

from __future__ import annotations

from pypdfbox.fontbox.ttf.glyph_positioning_table import GlyphPositioningTable


class _GposWrapperNoTable:
    """fontTools GPOS wrapper whose ``.table`` is ``None`` (undecoded)."""

    table = None


class _FakeTTFont:
    """Minimal fontTools ``TTFont`` stand-in for population."""

    def __init__(self) -> None:
        self._tables = {"GPOS": _GposWrapperNoTable()}

    def __getitem__(self, key: str) -> object:
        return self._tables[key]

    def getGlyphOrder(self) -> list[str]:  # noqa: N802 — fontTools API name
        return [".notdef", "A", "B"]


def test_populate_with_no_parsed_gpos_table_skips_tag_harvest() -> None:
    """A GPOS wrapper with ``table=None`` takes the ``_gpos_table is not
    None`` False arc ([128,140]); the script / feature tag lists are
    empty but glyph-order maps are still built."""
    table = GlyphPositioningTable()
    table.populate_from_fonttools(_FakeTTFont())
    assert table.get_supported_script_tags() == set()
    assert table.get_supported_feature_tags() == []
    assert table.initialized is True
