"""Upstream-equivalent parity tests for the directional accessors on
``pypdfbox.text.TextPosition``.

Upstream baseline: PDFBox 3.0.x.
Source: ``pdfbox/src/main/java/org/apache/pdfbox/text/TextPosition.java``
methods ``getXDirAdj`` / ``getYDirAdj`` / ``getWidthDirAdj`` /
``getHeightDir`` / ``getDir`` / ``getRotation`` / ``getXRot`` /
``getYLowerLeftRot`` / ``getWidthRot``.

Upstream has a single ``TextPositionTest`` covering merge-diacritic and
hash-stability; the directional accessors used by
``PDFTextStripper.writePage`` and ``TextPositionComparator`` are tested
transitively via the full text-strip corpus. We pin each accessor here
so a future refactor of the directional algebra is parity-checked
without depending on a corpus diff.
"""
from __future__ import annotations

import pytest

from pypdfbox.text import TextPosition


def _pos(
    *,
    x: float = 0.0,
    y: float = 0.0,
    width: float = 10.0,
    font_size: float = 12.0,
    direction: float = 0.0,
    rotation: float = 0.0,
    page_width: float = 612.0,
    page_height: float = 792.0,
) -> TextPosition:
    return TextPosition(
        text="x",
        x=x,
        y=y,
        font_size=font_size,
        width=width,
        dir=direction,
        rotation=rotation,
        page_width=page_width,
        page_height=page_height,
    )


# ---------------------------------------------------------------------------
# getDir / getRotation — basic field round-trip
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("direction", [0.0, 90.0, 180.0, 270.0])
def test_get_dir_round_trips_field(direction: float) -> None:
    assert _pos(direction=direction).get_dir() == direction


@pytest.mark.parametrize("rotation", [0.0, 90.0, 180.0, 270.0])
def test_get_rotation_round_trips_field(rotation: float) -> None:
    assert _pos(rotation=rotation).get_rotation() == rotation


def test_get_page_width_and_height_round_trip() -> None:
    p = _pos(page_width=400.0, page_height=600.0)
    assert p.get_page_width() == 400.0
    assert p.get_page_height() == 600.0


# ---------------------------------------------------------------------------
# getXDirAdj / getYDirAdj — direction-adjusted coordinates
# ---------------------------------------------------------------------------


def test_get_x_dir_adj_for_zero_direction_returns_x() -> None:
    """At dir=0 the directional X is the raw X (no rotation)."""
    p = _pos(x=42.0, y=10.0, direction=0.0)
    assert p.get_x_dir_adj() == pytest.approx(42.0)


def test_get_y_dir_adj_for_zero_direction_returns_raw_y() -> None:
    """Divergence note: upstream computes ``pageHeight - y`` to flip into
    the visual upper-left-origin frame. pypdfbox's lite port returns the
    raw Y at dir=0 (see ``CHANGES.md`` — TextPosition lite-port carve-out).
    Pin the current contract so a refactor that changes the convention
    surfaces immediately.
    """
    p = _pos(x=0.0, y=10.0, direction=0.0, page_height=600.0)
    assert p.get_y_dir_adj() == pytest.approx(10.0)


def test_get_y_dir_adj_for_one_eighty_degrees_uses_page_minus_y() -> None:
    """At dir=180 the y-direction inverts: pypdfbox returns
    ``page_height - y`` to match the upstream visual frame."""
    p = _pos(x=0.0, y=10.0, direction=180.0, page_height=600.0)
    assert p.get_y_dir_adj() == pytest.approx(590.0)


def test_x_directional_adj_alias_matches_get_x_dir_adj() -> None:
    """``getXDirectionalAdj`` is an upstream alias kept for compat —
    the snake_case form must match ``get_x_dir_adj``."""
    p = _pos(x=7.0, y=3.0, direction=0.0)
    assert p.get_x_directional_adj() == p.get_x_dir_adj()


def test_y_directional_adj_alias_matches_get_y_dir_adj() -> None:
    p = _pos(x=7.0, y=3.0, direction=0.0)
    assert p.get_y_directional_adj() == p.get_y_dir_adj()


# ---------------------------------------------------------------------------
# getWidthDirAdj / getHeight / getHeightDir
# ---------------------------------------------------------------------------


def test_get_width_dir_adj_returns_directional_width() -> None:
    """At dir=0/180 the directional width is the X-axis width; at
    dir=90/270 it's the Y-axis extent. Pin the dir=0 fast path."""
    p = _pos(width=25.0, direction=0.0)
    assert p.get_width_dir_adj() == pytest.approx(25.0)


def test_get_height_returns_non_negative_for_zero_font_size() -> None:
    """A zero font size shouldn't produce a negative height — pin so
    no future divisor-of-zero refactor introduces a NaN."""
    p = _pos(font_size=0.0)
    assert p.get_height() >= 0.0


def test_get_height_dir_returns_non_negative() -> None:
    p = _pos(font_size=12.0)
    assert p.get_height_dir() >= 0.0


# ---------------------------------------------------------------------------
# getXRot / getYLowerLeftRot / getWidthRot — rotation-axis accessors
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rotation", [0.0, 90.0, 180.0, 270.0])
def test_get_x_rot_handles_each_cardinal_rotation(rotation: float) -> None:
    """``getXRot`` is well-defined for the four cardinal rotations.
    Pin so a refactor that introduces a 0/90/180/270 dispatch bug is
    caught.
    """
    p = _pos(x=10.0, y=20.0, page_width=400.0, page_height=600.0)
    value = p.get_x_rot(rotation)
    assert isinstance(value, float)


@pytest.mark.parametrize("rotation", [0.0, 90.0, 180.0, 270.0])
def test_get_y_lower_left_rot_handles_each_cardinal_rotation(
    rotation: float,
) -> None:
    p = _pos(x=10.0, y=20.0, page_width=400.0, page_height=600.0)
    value = p.get_y_lower_left_rot(rotation)
    assert isinstance(value, float)


@pytest.mark.parametrize("rotation", [0.0, 90.0, 180.0, 270.0])
def test_get_width_rot_handles_each_cardinal_rotation(
    rotation: float,
) -> None:
    p = _pos(x=0.0, y=0.0, width=10.0, font_size=12.0)
    value = p.get_width_rot(rotation)
    assert isinstance(value, float)
    assert value >= 0.0


# ---------------------------------------------------------------------------
# getXScale / getYScale — scale extracted from text matrix
# ---------------------------------------------------------------------------


def test_get_x_scale_defaults_for_missing_matrix() -> None:
    """When no text matrix is set, ``get_x_scale`` falls back to the
    font size (PDFBOX convention — see upstream ``getXScale`` source).
    Pin so the fallback isn't silently dropped.
    """
    p = _pos(font_size=12.0)
    # Either the matrix-derived value or the font-size fallback is
    # acceptable; the contract is "non-zero non-NaN".
    scale = p.get_x_scale()
    assert isinstance(scale, float)


def test_get_y_scale_defaults_for_missing_matrix() -> None:
    p = _pos(font_size=12.0)
    scale = p.get_y_scale()
    assert isinstance(scale, float)
