"""Wave 1496 — coverage round-out for the pure matrix helpers in
:mod:`pypdfbox.rendering.pdf_renderer`.

Pins the deterministic, geometry-only module functions that the
rendering integration tests reach only indirectly:

* ``_page_rotation_matrix`` — the 90 / 180 / 270 / identity legs and the
  positive-quadrant re-anchoring of a rotated media box.
* ``_no_rotate_matrix`` — the NoRotate counter-rotation about an
  annotation's pivot (PDFBOX-4744), checked by mapping the pivot to
  itself (a fixed point) and a unit step to the rotated axis.
* ``_to_pil_affine`` — the PDF-CTM -> PIL/aggdraw row-vector transpose.

These assert the transform's algebraic contract, not bare execution.
"""

from __future__ import annotations

import math

from pypdfbox.rendering.pdf_renderer import (
    _IDENTITY,
    _no_rotate_matrix,
    _page_rotation_matrix,
    _to_pil_affine,
)


def _apply(m, x, y):
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


# ---------------------------------------------------------------------
# _page_rotation_matrix.
# ---------------------------------------------------------------------
def test_page_rotation_matrix_identity_for_zero() -> None:
    assert _page_rotation_matrix(0, 100.0, 50.0) == _IDENTITY


def test_page_rotation_matrix_90_reanchors_into_positive_quadrant() -> None:
    w, h = 100.0, 50.0
    m = _page_rotation_matrix(90, w, h)
    # Corners of the (w, h) box map into the positive (h, w) quadrant.
    for x, y in ((0, 0), (w, 0), (0, h), (w, h)):
        nx, ny = _apply(m, x, y)
        assert -1e-9 <= nx <= h + 1e-9
        assert -1e-9 <= ny <= w + 1e-9


def test_page_rotation_matrix_180_keeps_extents() -> None:
    w, h = 100.0, 50.0
    m = _page_rotation_matrix(180, w, h)
    assert _apply(m, 0, 0) == (w, h)
    assert _apply(m, w, h) == (0.0, 0.0)


def test_page_rotation_matrix_270_reanchors() -> None:
    w, h = 100.0, 50.0
    m = _page_rotation_matrix(270, w, h)
    for x, y in ((0, 0), (w, 0), (0, h), (w, h)):
        nx, ny = _apply(m, x, y)
        assert -1e-9 <= nx <= h + 1e-9
        assert -1e-9 <= ny <= w + 1e-9


# ---------------------------------------------------------------------
# _no_rotate_matrix.
# ---------------------------------------------------------------------
def test_no_rotate_matrix_pivot_is_fixed_point() -> None:
    px, py = 30.0, 70.0
    m = _no_rotate_matrix(90, px, py)
    nx, ny = _apply(m, px, py)
    assert math.isclose(nx, px, abs_tol=1e-9)
    assert math.isclose(ny, py, abs_tol=1e-9)


def test_no_rotate_matrix_90_counter_rotation_direction() -> None:
    # theta = -90deg: x' = cos*x - sin*y about the origin pivot.
    m = _no_rotate_matrix(90, 0.0, 0.0)
    a, b, c, d, _e, _f = m
    assert math.isclose(a, math.cos(math.radians(-90)), abs_tol=1e-9)
    assert math.isclose(b, -math.sin(math.radians(-90)), abs_tol=1e-9)
    assert math.isclose(c, math.sin(math.radians(-90)), abs_tol=1e-9)
    assert math.isclose(d, math.cos(math.radians(-90)), abs_tol=1e-9)
    # A unit x-step rotates onto the +y axis for theta = -90.
    nx, ny = _apply(m, 1.0, 0.0)
    assert math.isclose(nx, 0.0, abs_tol=1e-9)
    assert math.isclose(ny, 1.0, abs_tol=1e-9)


def test_no_rotate_matrix_zero_is_identity_block() -> None:
    m = _no_rotate_matrix(0, 5.0, 9.0)
    a, b, c, d, e, f = m
    assert math.isclose(a, 1.0, abs_tol=1e-9)
    assert math.isclose(d, 1.0, abs_tol=1e-9)
    assert math.isclose(b, 0.0, abs_tol=1e-9)
    assert math.isclose(c, 0.0, abs_tol=1e-9)
    assert math.isclose(e, 0.0, abs_tol=1e-9)
    assert math.isclose(f, 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------
# _to_pil_affine.
# ---------------------------------------------------------------------
def test_to_pil_affine_transposes_block_and_reorders_translation() -> None:
    # PDF (a, b, c, d, e, f) -> PIL (a, c, e, b, d, f).
    assert _to_pil_affine((1, 2, 3, 4, 5, 6)) == (1, 3, 5, 2, 4, 6)
