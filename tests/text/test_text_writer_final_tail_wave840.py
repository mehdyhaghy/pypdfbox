from __future__ import annotations

from unittest.mock import patch

import pytest

from pypdfbox.cos import COSObjectKey, COSString
from pypdfbox.pdfwriter.cos_writer_xref_entry import COSWriterXRefEntry
from pypdfbox.text import FilteredTextStripper, PDFTextStripperByArea, TextPosition
from pypdfbox.text.pdf_text_stripper import PDFTextStripper, _TextState


def _position(angle_90: bool = False) -> TextPosition:
    matrix = [0.0, 1.0, -1.0, 0.0, 0.0, 0.0] if angle_90 else None
    return TextPosition(
        text="x",
        x=10.0,
        y=20.0,
        font_size=12.0,
        width=6.0,
        text_matrix=matrix,
    )


def test_wave840_by_area_duplicate_region_appends_name_overwrites_bounds() -> None:
    stripper = PDFTextStripperByArea()

    stripper.add_region("body", (0, 0, 10, 10))
    stripper.add_region("margin", (20, 20, 5, 5))
    stripper.add_region("body", (2, 3, 4, 5))

    # Upstream parity (wave 1551, verified live vs PDFBox 3.0.7): ``addRegion``
    # unconditionally appends to the ``regions`` ArrayList, so a re-added name
    # appears twice in ``getRegions()`` while the ``regionArea`` HashMap keeps
    # only the last rect. Previously asserted dedup (``["body", "margin"]``);
    # retargeted when the live oracle proved the duplicate.
    assert stripper.get_regions() == ["body", "margin", "body"]
    assert stripper._region_area["body"] == (2.0, 3.0, 6.0, 8.0)


def test_wave840_by_area_remove_region_clears_cached_text() -> None:
    stripper = PDFTextStripperByArea()
    stripper.add_region("body", (0, 0, 10, 10))
    stripper._region_text["body"] = "stale"
    stripper._region_character_list["body"] = [_position()]

    stripper.remove_region("body")

    assert stripper.get_regions() == []
    assert stripper.get_text_for_region("body") == ""
    assert "body" not in stripper._region_character_list


def test_wave840_filtered_emit_returns_before_base_emit_when_angle_differs() -> None:
    state = _TextState()
    state.tm_b = 1.0
    state.tm_d = 0.0
    positions: list[TextPosition] = []
    stripper = FilteredTextStripper(target_angle=0)

    with patch.object(PDFTextStripper, "_emit") as base_emit:
        stripper._emit(COSString("ignored"), state, positions)

    base_emit.assert_not_called()
    assert positions == []


def test_wave840_filtered_emit_delegates_when_angle_matches() -> None:
    state = _TextState()
    positions: list[TextPosition] = []
    text = COSString("shown")
    stripper = FilteredTextStripper(target_angle=0)

    with patch.object(PDFTextStripper, "_emit") as base_emit:
        stripper._emit(text, state, positions)

    base_emit.assert_called_once_with(text, state, positions)


def test_wave840_filtered_process_text_position_normalizes_target_angle() -> None:
    stripper = FilteredTextStripper(target_angle=-270)
    pos90 = _position(angle_90=True)
    pos0 = _position(angle_90=False)

    with patch.object(PDFTextStripper, "process_text_position") as base_hook:
        stripper.process_text_position(pos90)
        stripper.process_text_position(pos0)

    base_hook.assert_called_once_with(pos90)


def test_wave840_xref_entry_non_entry_le_ge_return_not_implemented() -> None:
    entry = COSWriterXRefEntry(offset=0, key=COSObjectKey(4, 0))

    with pytest.raises(TypeError):
        assert entry <= object()
    with pytest.raises(TypeError):
        assert entry >= object()
