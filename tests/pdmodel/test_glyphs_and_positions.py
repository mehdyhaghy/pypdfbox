"""Tests for :class:`pypdfbox.pdmodel.glyphs_and_positions.GlyphsAndPositions`.

Ported alongside upstream's PDFBOX-4951 glyph-layout core
(``org.apache.pdfbox.pdmodel.GlyphsAndPositions``). Upstream ships no unit
test for this class in the core ``pdfbox`` artifact — its only coverage comes
from the optional ``pdfbox-layout-awt`` / ``pdfbox-layout-fop`` backend
modules, which pypdfbox deliberately does not port (no text-shaping
dependency). These are hand-written equivalents.
"""

import pytest

from pypdfbox.pdmodel import GlyphsAndPositions


def test_new_instance_is_empty() -> None:
    gap = GlyphsAndPositions()
    assert gap.is_empty()
    assert gap.to_array() == []


def test_adjacent_glyphs_collect_into_one_sub_list() -> None:
    gap = GlyphsAndPositions()
    gap.add(3)
    gap.add(4)
    gap.add(5)
    entries = gap.to_array()
    assert len(entries) == 1
    assert isinstance(entries[0], GlyphsAndPositions.GlyphSubList)
    assert entries[0].to_int_array() == [3, 4, 5]
    assert not gap.is_empty()


def test_position_starts_a_new_sub_list() -> None:
    gap = GlyphsAndPositions()
    gap.add(3)
    gap.add(4)
    gap.add(-120.0)
    gap.add(5)
    entries = gap.to_array()
    assert len(entries) == 3
    assert entries[0].to_int_array() == [3, 4]
    assert entries[1] == -120.0
    assert isinstance(entries[1], float)
    assert entries[2].to_int_array() == [5]


def test_leading_position_is_kept_as_first_entry() -> None:
    gap = GlyphsAndPositions()
    gap.add(-50.0)
    gap.add(7)
    entries = gap.to_array()
    assert entries[0] == -50.0
    assert entries[1].to_int_array() == [7]


def test_consecutive_positions_are_kept_separate() -> None:
    gap = GlyphsAndPositions()
    gap.add(-10.0)
    gap.add(-20.0)
    assert gap.to_array() == [-10.0, -20.0]


def test_clear_resets_to_empty() -> None:
    gap = GlyphsAndPositions()
    gap.add(1)
    gap.add(2.5)
    assert not gap.is_empty()
    gap.clear()
    assert gap.is_empty()
    assert gap.to_array() == []


def test_to_array_returns_a_copy() -> None:
    gap = GlyphsAndPositions()
    gap.add(1)
    snapshot = gap.to_array()
    snapshot.append("tampered")
    assert len(gap.to_array()) == 1


def test_glyph_sub_list_is_a_list() -> None:
    sub = GlyphsAndPositions.GlyphSubList()
    sub.append(1)
    sub.append(2)
    assert isinstance(sub, list)
    assert sub.to_int_array() == [1, 2]
    assert GlyphsAndPositions.GlyphSubList().to_int_array() == []


def test_add_rejects_bool() -> None:
    gap = GlyphsAndPositions()
    with pytest.raises(TypeError):
        gap.add(True)


def test_add_rejects_other_types() -> None:
    gap = GlyphsAndPositions()
    with pytest.raises(TypeError):
        gap.add("3")  # type: ignore[arg-type]
