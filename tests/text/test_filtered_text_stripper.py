"""Hand-written tests for :mod:`pypdfbox.text.filtered_text_stripper`.

Synthesises a single-page PDF where the same content stream lays down
text at four rotations (0, 90, 180, 270 degrees) via four ``Tm``
matrices, then verifies:

* ``get_angle`` recovers the rotation from a synthetic
  :class:`TextPosition`.
* :class:`AngleCollector` records every distinct rotation seen.
* :class:`FilteredTextStripper(target_angle=...)` only emits the run
  whose text matrix matches the requested angle.
"""
from __future__ import annotations

import math
from pathlib import Path
from unittest.mock import patch

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import (
    AngleCollector,
    FilteredTextStripper,
    PDFTextStripper,
    TextPosition,
    get_angle,
)
from pypdfbox.text.filtered_text_stripper import get_angle_from_matrix

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _rotation_matrix(angle_degrees: int) -> tuple[float, float, float, float]:
    """Return the ``(a, b, c, d)`` columns of a 2x2 rotation matrix —
    the same shape PDF uses in ``a b c d e f Tm``.
    """
    rad = math.radians(angle_degrees)
    cos = math.cos(rad)
    sin = math.sin(rad)
    # Snap near-zero floats to exact zero so the synthesised content
    # stream stays small and round-trips cleanly through the parser.
    if abs(cos) < 1e-12:
        cos = 0.0
    if abs(sin) < 1e-12:
        sin = 0.0
    return cos, sin, -sin, cos


def _build_mixed_rotation_page(doc: PDDocument) -> PDPage:
    """Lay down four text objects, one per cardinal rotation, each
    carrying its angle in the displayed string for easy assertions.
    """
    page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
    parts: list[bytes] = []
    rotations = (
        (0, 100, 700, "ANGLE0"),
        (90, 200, 500, "ANGLE90"),
        (180, 300, 400, "ANGLE180"),
        (270, 400, 300, "ANGLE270"),
    )
    for angle, e, f, label in rotations:
        a, b, c, d = _rotation_matrix(angle)
        parts.append(
            f"BT /F0 12 Tf {a:g} {b:g} {c:g} {d:g} {e} {f} Tm "
            f"({label}) Tj ET\n".encode("latin-1")
        )
    stream = COSStream()
    stream.set_data(b"".join(parts))
    page.set_contents(stream)
    doc.add_page(page)
    return page


# ---------------------------------------------------------------------------
# get_angle
# ---------------------------------------------------------------------------


def test_get_angle_zero_for_identity_matrix() -> None:
    pos = TextPosition(
        text="x", x=0.0, y=0.0, font_size=12.0,
        text_matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
    )
    assert get_angle(pos) == 0


def test_get_angle_recovers_each_cardinal_rotation() -> None:
    for angle in (0, 90, 180, 270):
        a, b, c, d = _rotation_matrix(angle)
        pos = TextPosition(
            text="x", x=0.0, y=0.0, font_size=12.0,
            text_matrix=[a, b, c, d, 0.0, 0.0],
        )
        assert get_angle(pos) == angle


def test_get_angle_normalises_to_unsigned() -> None:
    # ``-90`` rotation matrix should round-trip to ``270`` degrees.
    a, b, c, d = _rotation_matrix(-90)
    pos = TextPosition(
        text="x", x=0.0, y=0.0, font_size=12.0,
        text_matrix=[a, b, c, d, 0.0, 0.0],
    )
    assert get_angle(pos) == 270


def test_get_angle_handles_missing_matrix() -> None:
    pos = TextPosition(text="x", x=0.0, y=0.0, font_size=12.0)
    assert get_angle(pos) == 0


# ---------------------------------------------------------------------------
# AngleCollector
# ---------------------------------------------------------------------------


def test_angle_collector_picks_up_every_rotation(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        _build_mixed_rotation_page(doc)
        out = tmp_path / "mixed.pdf"
        doc.save(out)
    finally:
        doc.close()

    doc = PDDocument.load(out)
    try:
        collector = AngleCollector()
        collector.set_start_page(1)
        collector.set_end_page(1)
        text = collector.get_text(doc)
        assert text.strip() == ""
        assert collector.get_angles() == {0, 90, 180, 270}
    finally:
        doc.close()


def test_angle_collector_public_process_text_position_collects_angle() -> None:
    _, b, _, d = _rotation_matrix(90)
    pos = TextPosition(
        text="x", x=0.0, y=0.0, font_size=12.0,
        text_matrix=[1.0, b, 0.0, d, 0.0, 0.0],
    )
    collector = AngleCollector()
    collector.process_text_position(pos)
    assert collector.get_angles() == {90}


def test_wave325_angle_collector_ignores_empty_show_text(tmp_path: Path) -> None:
    doc = PDDocument()
    try:
        page = PDPage(PDRectangle(0.0, 0.0, 612.0, 792.0))
        stream = COSStream()
        stream.set_data(
            b"BT /F0 12 Tf 0 1 -1 0 100 700 Tm () Tj ET\n"
            b"BT /F0 12 Tf 1 0 0 1 100 600 Tm (VISIBLE) Tj ET\n"
        )
        page.set_contents(stream)
        doc.add_page(page)
        out = tmp_path / "empty-angle.pdf"
        doc.save(out)
    finally:
        doc.close()

    doc = PDDocument.load(out)
    try:
        collector = AngleCollector()
        assert collector.get_text(doc).strip() == ""
        assert collector.get_angles() == {0}
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# FilteredTextStripper
# ---------------------------------------------------------------------------


def test_filtered_text_stripper_default_target_is_zero() -> None:
    stripper = FilteredTextStripper()
    assert stripper.get_target_angle() == 0


def test_filtered_text_stripper_target_angle_setter_normalises() -> None:
    stripper = FilteredTextStripper()
    stripper.set_target_angle(-90)
    assert stripper.get_target_angle() == 270
    stripper.set_target_angle(450)
    assert stripper.get_target_angle() == 90


def test_filtered_text_stripper_should_skip_glyph_uses_public_angle_helper() -> None:
    _, b, _, d = _rotation_matrix(90)
    pos = TextPosition(
        text="x", x=0.0, y=0.0, font_size=12.0,
        text_matrix=[1.0, b, 0.0, d, 0.0, 0.0],
    )
    stripper = FilteredTextStripper(target_angle=90)
    assert stripper.should_skip_glyph(pos) is False
    stripper.set_target_angle(0)
    assert stripper.should_skip_glyph(pos) is True


def test_filtered_text_stripper_process_text_position_delegates_only_on_match() -> None:
    pos90 = TextPosition(
        text="vertical", x=0.0, y=0.0, font_size=12.0,
        text_matrix=[0.0, 1.0, -1.0, 0.0, 0.0, 0.0],
    )
    pos0 = TextPosition(
        text="horizontal", x=0.0, y=0.0, font_size=12.0,
        text_matrix=[1.0, 0.0, 0.0, 1.0, 0.0, 0.0],
    )
    stripper = FilteredTextStripper(target_angle=90)

    with patch.object(PDFTextStripper, "process_text_position") as base_hook:
        stripper.process_text_position(pos90)
        stripper.process_text_position(pos0)

    base_hook.assert_called_once_with(pos90)


def _extract(stripper: PDFTextStripper, doc: PDDocument) -> str:
    stripper.set_start_page(1)
    stripper.set_end_page(1)
    return stripper.get_text(doc)


def test_filtered_text_stripper_emits_only_matching_rotation(
    tmp_path: Path,
) -> None:
    doc = PDDocument()
    try:
        _build_mixed_rotation_page(doc)
        out = tmp_path / "mixed.pdf"
        doc.save(out)
    finally:
        doc.close()

    expected = {0: "ANGLE0", 90: "ANGLE90", 180: "ANGLE180", 270: "ANGLE270"}

    doc = PDDocument.load(out)
    try:
        for target, label in expected.items():
            text = _extract(FilteredTextStripper(target_angle=target), doc)
            # Only the matching label should survive the filter.
            assert label in text
            for other_target, other_label in expected.items():
                if other_target == target:
                    continue
                assert other_label not in text
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# get_angle_from_matrix
# ---------------------------------------------------------------------------


def test_get_angle_from_matrix_handles_each_cardinal_rotation() -> None:
    for angle in (0, 90, 180, 270):
        a, b, c, d = _rotation_matrix(angle)
        assert get_angle_from_matrix([a, b, c, d, 0.0, 0.0]) == angle


def test_get_angle_from_matrix_returns_zero_for_none_or_short() -> None:
    assert get_angle_from_matrix(None) == 0
    assert get_angle_from_matrix([1.0, 0.0]) == 0


def test_get_angle_from_matrix_accepts_tuple_and_normalises_negative() -> None:
    a, b, c, d = _rotation_matrix(-90)
    assert get_angle_from_matrix((a, b, c, d, 0.0, 0.0)) == 270


def test_get_angle_delegates_to_get_angle_from_matrix() -> None:
    a, b, c, d = _rotation_matrix(180)
    pos = TextPosition(
        text="x", x=0.0, y=0.0, font_size=12.0,
        text_matrix=[a, b, c, d, 0.0, 0.0],
    )
    assert get_angle(pos) == get_angle_from_matrix(pos.get_text_matrix())


# ---------------------------------------------------------------------------
# AngleCollector — Pythonic Set helpers
# ---------------------------------------------------------------------------


def test_angle_collector_clear_angles_resets_state() -> None:
    collector = AngleCollector()
    collector._angles.update({0, 90, 180})
    collector.clear_angles()
    assert collector.get_angles() == set()
    assert collector.get_sorted_angles() == []


def test_angle_collector_get_sorted_angles_returns_ascending_list() -> None:
    collector = AngleCollector()
    collector._angles.update({270, 0, 180, 90})
    assert collector.get_sorted_angles() == [0, 90, 180, 270]


def test_angle_collector_has_angle_normalises_input() -> None:
    collector = AngleCollector()
    collector._angles.add(270)
    assert collector.has_angle(270) is True
    # ``-90`` → ``270`` after normalisation, so should match.
    assert collector.has_angle(-90) is True
    assert collector.has_angle(90) is False


def test_angle_collector_contains_supports_in_operator() -> None:
    collector = AngleCollector()
    collector._angles.update({0, 180})
    assert 0 in collector
    assert 180 in collector
    assert 90 not in collector
    # ``-180`` normalises to ``180``.
    assert -180 in collector
    # Non-numeric input falls back to ``False`` rather than raising.
    assert "bogus" not in collector


def test_angle_collector_len_and_iter_match_sorted_view() -> None:
    collector = AngleCollector()
    collector._angles.update({90, 0, 270})
    assert len(collector) == 3
    assert list(iter(collector)) == [0, 90, 270]


# ---------------------------------------------------------------------------
# FilteredTextStripper.is_target_angle
# ---------------------------------------------------------------------------


def test_filtered_text_stripper_is_target_angle_matches_after_normalisation() -> None:
    stripper = FilteredTextStripper(target_angle=270)
    assert stripper.is_target_angle(270) is True
    assert stripper.is_target_angle(-90) is True  # -90 → 270
    assert stripper.is_target_angle(0) is False
    stripper.set_target_angle(0)
    assert stripper.is_target_angle(360) is True  # 360 → 0
    assert stripper.is_target_angle(90) is False


def test_unfiltered_stripper_still_sees_everything(tmp_path: Path) -> None:
    """Sanity check: the *unfiltered* parent stripper must still emit
    every rotation, otherwise the filter test above is vacuous.
    """
    doc = PDDocument()
    try:
        _build_mixed_rotation_page(doc)
        out = tmp_path / "mixed.pdf"
        doc.save(out)
    finally:
        doc.close()

    doc = PDDocument.load(out)
    try:
        text = _extract(PDFTextStripper(), doc)
        for label in ("ANGLE0", "ANGLE90", "ANGLE180", "ANGLE270"):
            assert label in text
    finally:
        doc.close()
