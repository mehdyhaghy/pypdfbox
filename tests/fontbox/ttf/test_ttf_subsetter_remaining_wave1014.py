from __future__ import annotations

from tests.fontbox.ttf import test_ttf_subsetter_remaining_wave754 as target


def test_fake_source_ttf_cmap_subtable_returns_none() -> None:
    source = target._FakeSourceTTF(object())

    assert source.get_unicode_cmap_subtable() is None


def test_no_glyf_source_table_glyph_order() -> None:
    assert target._NoGlyfSourceTable().getGlyphOrder() == [".notdef"]
