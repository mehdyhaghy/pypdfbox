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

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import (
    AngleCollector,
    FilteredTextStripper,
    PDFTextStripper,
    TextPosition,
    get_angle,
)


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
        collector.get_text(doc)
        assert collector.get_angles() == {0, 90, 180, 270}
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
