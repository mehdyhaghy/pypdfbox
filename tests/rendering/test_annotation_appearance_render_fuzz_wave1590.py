"""Wave 1590 — fuzz / white-box battery for the annotation appearance
matrix algorithm in :meth:`PDFRenderer._render_annotation`.

The PDF spec (32000-1 §12.5.5) and upstream PDFBox
``PDFStreamEngine.processAnnotation`` map an annotation's Normal
Appearance form XObject onto the annotation ``/Rect`` like this:

1. Take the appearance form's ``/BBox`` and its ``/Matrix``.
2. Transform the four ``/BBox`` corners by ``/Matrix`` and take the
   axis-aligned bounding box of the result — the *transformed
   appearance box* (``transformedBox``).
3. Build matrix ``a`` that maps ``transformedBox`` onto ``/Rect``:
   translate ``transformedBox`` lower-left to the origin, scale by
   ``rect.w / tBox.w`` and ``rect.h / tBox.h``, then translate to the
   rect lower-left::

       a = T(rect.llx, rect.lly)
           · S(rect.w / tBox.w, rect.h / tBox.h)
           · T(-tBox.llx, -tBox.lly)

4. Concatenate the appearance ``/Matrix`` *first*, then ``a``
   (upstream ``Matrix.concatenate(a, matrix)`` ≡ ``matrix.multiply(a)``)
   — pypdfbox's ``_matmul(m_appear, a_matrix)`` (apply ``m_appear``
   first). The composite is then concatenated onto the page CTM.

These tests reconstruct the spec algorithm independently and assert the
renderer's actual composed CTM matches it across: identity matrices,
pure-scale rects (rect bigger / smaller than bbox), translated rects,
rotated ``/Matrix`` values (90 / 180 / 270 / skew), and degenerate
(zero-width / zero-height) transformed boxes (no divide-by-zero, silent
skip). The Hidden / NoView visibility flags are exercised to confirm
they short-circuit before any appearance work.

White-box: the renderer is driven with light fake annotation /
appearance objects and its path / clip / content-walk methods are
stubbed so each invocation records only the composed ``self._gs.ctm``.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from pypdfbox.rendering.pdf_renderer import (
    _IDENTITY,
    PDFRenderer,
    _GState,
    _matmul,
)

# ----------------------------------------------------------------------
# Reference implementation of the spec §12.5.5 appearance matrix. Built
# from first principles so it is an *independent* oracle for the
# renderer's composition, not a copy of it.
# ----------------------------------------------------------------------


def _transform_corner(m: tuple[float, ...], x: float, y: float) -> tuple[float, float]:
    """``[x y 1] · m`` in the renderer's row-vector PDF convention."""
    a, b, c, d, e, f = m
    return (a * x + c * y + e, b * x + d * y + f)


def _reference_appearance_ctm(
    bbox: tuple[float, float, float, float],
    matrix: tuple[float, float, float, float, float, float],
    rect: tuple[float, float, float, float],
) -> tuple[float, ...] | None:
    """Return the composed appearance CTM per the spec algorithm, or
    ``None`` for a degenerate transformed box / rect (which the renderer
    must silently skip)."""
    bllx, blly, burx, bury = bbox
    rllx, rlly, rurx, rury = rect
    rect_w = rurx - rllx
    rect_h = rury - rlly
    if rect_w <= 0 or rect_h <= 0:
        return None
    if (burx - bllx) <= 0 or (bury - blly) <= 0:
        return None
    corners = [
        (bllx, blly),
        (burx, blly),
        (burx, bury),
        (bllx, bury),
    ]
    txs = []
    tys = []
    for cx, cy in corners:
        tx, ty = _transform_corner(matrix, cx, cy)
        txs.append(tx)
        tys.append(ty)
    tb_x = min(txs)
    tb_y = min(tys)
    tb_w = max(txs) - tb_x
    tb_h = max(tys) - tb_y
    if tb_w <= 0 or tb_h <= 0:
        return None
    sx = rect_w / tb_w
    sy = rect_h / tb_h
    a_matrix = (sx, 0.0, 0.0, sy, rllx - tb_x * sx, rlly - tb_y * sy)
    return _matmul(matrix, a_matrix)


# ----------------------------------------------------------------------
# Lightweight fakes for the annotation / appearance / rectangle objects
# the renderer duck-types over.
# ----------------------------------------------------------------------


class _FakeRect:
    def __init__(self, llx: float, lly: float, urx: float, ury: float) -> None:
        self._llx, self._lly, self._urx, self._ury = llx, lly, urx, ury

    def get_lower_left_x(self) -> float:
        return self._llx

    def get_lower_left_y(self) -> float:
        return self._lly

    def get_upper_right_x(self) -> float:
        return self._urx

    def get_upper_right_y(self) -> float:
        return self._ury

    def get_width(self) -> float:
        return self._urx - self._llx

    def get_height(self) -> float:
        return self._ury - self._lly


class _FakeBBox(_FakeRect):
    def get_bbox(self) -> _FakeRect:  # pragma: no cover - not used directly
        return self


class _FakeAppearance:
    def __init__(
        self,
        bbox: tuple[float, float, float, float],
        matrix: tuple[float, ...] | None,
    ) -> None:
        self._bbox = _FakeBBox(*bbox)
        self._matrix = matrix

    def get_bbox(self) -> _FakeBBox:
        return self._bbox

    def get_matrix(self) -> tuple[float, ...] | None:
        return self._matrix

    def get_resources(self) -> None:
        return None

    def get_cos_object(self) -> None:
        # Not a COSStream → the renderer skips the content walk; the
        # composed CTM is captured by the stubbed clip method first.
        return None


class _FakeAnnotation:
    def __init__(
        self,
        rect: tuple[float, float, float, float],
        appearance: _FakeAppearance | None,
        *,
        hidden: bool = False,
        no_view: bool = False,
        no_rotate: bool = False,
    ) -> None:
        self._rect = _FakeRect(*rect)
        self._appearance = appearance
        self._hidden = hidden
        self._no_view = no_view
        self._no_rotate = no_rotate

    def get_rectangle(self) -> _FakeRect:
        return self._rect

    def get_normal_appearance_stream(self) -> _FakeAppearance | None:
        return self._appearance

    def is_hidden(self) -> bool:
        return self._hidden

    def is_no_view(self) -> bool:
        return self._no_view

    def is_printed(self) -> bool:
        return True

    def is_no_rotate(self) -> bool:
        return self._no_rotate

    def get_optional_content(self) -> None:
        return None


# ----------------------------------------------------------------------
# Renderer harness: build a bare PDFRenderer, seed a single GState, and
# stub the path / clip / content-walk so _render_annotation records only
# the composed CTM.
# ----------------------------------------------------------------------


def _make_renderer(page_rotation: int = 0) -> tuple[PDFRenderer, list[tuple[float, ...]]]:
    r = PDFRenderer.__new__(PDFRenderer)
    r._document = None  # type: ignore[attr-defined]
    r._gs_stack = [_GState()]  # type: ignore[attr-defined]
    r._device_ctm = _IDENTITY  # type: ignore[attr-defined]
    r._render_page_rotation = page_rotation  # type: ignore[attr-defined]
    r._resources = None  # type: ignore[attr-defined]
    r._subpaths = []  # type: ignore[attr-defined]
    r._current_subpath = None  # type: ignore[attr-defined]
    r._pending_clip = None  # type: ignore[attr-defined]
    r._active_destination = "View"  # type: ignore[attr-defined]
    r._default_destination = "View"  # type: ignore[attr-defined]

    captured: list[tuple[float, ...]] = []

    def _capture_clip(*_a: Any, **_k: Any) -> None:
        captured.append(r._gs.ctm)

    def _start_subpath(_x: float, _y: float) -> None:
        # The renderer asserts ``_current_subpath is not None`` right
        # after this call (it then appends the bbox clip corners), so the
        # stub must establish a real list.
        r._current_subpath = []
        r._subpaths.append(r._current_subpath)

    # Stub everything _render_annotation calls between setting the CTM
    # and the content walk so no real raster machinery is needed.
    r._start_subpath = _start_subpath  # type: ignore[attr-defined]
    r._apply_pending_clip = _capture_clip  # type: ignore[attr-defined]
    r._reset_path = lambda *_a, **_k: None  # type: ignore[attr-defined]
    r._process_form_bytes = lambda *_a, **_k: None  # type: ignore[attr-defined]
    r._property_list_is_hidden = lambda *_a, **_k: False  # type: ignore[attr-defined]
    return r, captured


def _assert_matrix_close(
    got: tuple[float, ...], expected: tuple[float, ...], *, tol: float = 1e-4
) -> None:
    assert len(got) == 6
    for i, (g, e) in enumerate(zip(got, expected, strict=True)):
        assert math.isclose(g, e, rel_tol=tol, abs_tol=tol), (
            f"matrix component {i}: got {g}, expected {e} (full got={got}, "
            f"expected={expected})"
        )


# ----------------------------------------------------------------------
# Parametrised parity battery: composed CTM matches the spec reference.
# ----------------------------------------------------------------------

_IDENT_M = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

_CASES: list[tuple[str, tuple, tuple, tuple]] = [
    # (id, bbox, matrix, rect)
    ("identity_same_size", (0, 0, 100, 100), _IDENT_M, (0, 0, 100, 100)),
    ("identity_offset_rect", (0, 0, 100, 100), _IDENT_M, (50, 60, 150, 160)),
    ("scale_up_2x", (0, 0, 50, 50), _IDENT_M, (0, 0, 100, 100)),
    ("scale_down_half", (0, 0, 200, 200), _IDENT_M, (0, 0, 100, 100)),
    ("nonsquare_rect", (0, 0, 100, 100), _IDENT_M, (10, 20, 310, 120)),
    ("bbox_not_at_origin", (20, 30, 120, 130), _IDENT_M, (0, 0, 100, 100)),
    ("bbox_negative_origin", (-50, -50, 50, 50), _IDENT_M, (0, 0, 200, 200)),
    ("rect_offset_and_scale", (10, 10, 60, 110), _IDENT_M, (100, 200, 300, 600)),
    (
        "matrix_translate",
        (0, 0, 100, 100),
        (1.0, 0.0, 0.0, 1.0, 25.0, 40.0),
        (0, 0, 100, 100),
    ),
    (
        "matrix_scale2x",
        (0, 0, 100, 100),
        (2.0, 0.0, 0.0, 2.0, 0.0, 0.0),
        (0, 0, 100, 100),
    ),
    (
        "matrix_rot90",
        (0, 0, 100, 50),
        (0.0, 1.0, -1.0, 0.0, 0.0, 0.0),
        (0, 0, 100, 100),
    ),
    (
        "matrix_rot180",
        (0, 0, 80, 120),
        (-1.0, 0.0, 0.0, -1.0, 0.0, 0.0),
        (10, 10, 110, 210),
    ),
    (
        "matrix_rot270",
        (0, 0, 120, 40),
        (0.0, -1.0, 1.0, 0.0, 0.0, 0.0),
        (0, 0, 60, 200),
    ),
    (
        "matrix_skew",
        (0, 0, 100, 100),
        (1.0, 0.5, 0.3, 1.0, 0.0, 0.0),
        (0, 0, 100, 100),
    ),
    (
        "matrix_rot45",
        (0, 0, 100, 100),
        (
            math.cos(math.radians(45)),
            math.sin(math.radians(45)),
            -math.sin(math.radians(45)),
            math.cos(math.radians(45)),
            0.0,
            0.0,
        ),
        (0, 0, 200, 200),
    ),
    (
        "matrix_scale_and_translate",
        (0, 0, 50, 50),
        (3.0, 0.0, 0.0, 2.0, 10.0, 20.0),
        (5, 5, 305, 205),
    ),
    (
        "matrix_negative_scale_x",
        (0, 0, 100, 100),
        (-1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        (0, 0, 100, 100),
    ),
    (
        "tiny_bbox_huge_rect",
        (0, 0, 1, 1),
        _IDENT_M,
        (0, 0, 1000, 1000),
    ),
    (
        "huge_bbox_tiny_rect",
        (0, 0, 5000, 5000),
        _IDENT_M,
        (0, 0, 10, 10),
    ),
    (
        "fractional_everything",
        (1.5, 2.25, 101.5, 52.25),
        (1.1, 0.0, 0.0, 0.9, 3.3, -4.4),
        (12.5, 7.75, 212.5, 107.75),
    ),
]


@pytest.mark.parametrize(
    "bbox,matrix,rect",
    [(c[1], c[2], c[3]) for c in _CASES],
    ids=[c[0] for c in _CASES],
)
def test_appearance_ctm_matches_spec_reference(
    bbox: tuple, matrix: tuple, rect: tuple
) -> None:
    r, captured = _make_renderer()
    appearance = _FakeAppearance(bbox, matrix)
    annot = _FakeAnnotation(rect, appearance)
    r._render_annotation(annot)
    expected = _reference_appearance_ctm(bbox, matrix, rect)
    assert expected is not None, "test case unexpectedly degenerate"
    assert len(captured) == 1, "appearance was skipped — expected one render"
    _assert_matrix_close(captured[0], expected)


def test_appearance_ctm_maps_bbox_corners_onto_rect() -> None:
    """End-to-end geometric check: the transformed-bbox lower-left corner
    must land on the rect lower-left, and the transformed-bbox extent
    must scale exactly to the rect extent (identity /Matrix)."""
    bbox = (0.0, 0.0, 40.0, 80.0)
    rect = (100.0, 200.0, 300.0, 600.0)  # 200 x 400
    r, captured = _make_renderer()
    r._render_annotation(_FakeAnnotation(rect, _FakeAppearance(bbox, _IDENT_M)))
    assert len(captured) == 1
    ctm = captured[0]
    # bbox lower-left (0,0) -> rect lower-left (100,200)
    ll = _transform_corner(ctm, 0.0, 0.0)
    assert math.isclose(ll[0], 100.0, abs_tol=1e-4)
    assert math.isclose(ll[1], 200.0, abs_tol=1e-4)
    # bbox upper-right (40,80) -> rect upper-right (300,600)
    ur = _transform_corner(ctm, 40.0, 80.0)
    assert math.isclose(ur[0], 300.0, abs_tol=1e-4)
    assert math.isclose(ur[1], 600.0, abs_tol=1e-4)


# ----------------------------------------------------------------------
# Degenerate transformed boxes must not divide-by-zero — silent skip.
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    "bbox,matrix",
    [
        # Zero-width bbox.
        ((0, 0, 0, 100), _IDENT_M),
        # Zero-height bbox.
        ((0, 0, 100, 0), _IDENT_M),
        # Matrix collapses x extent (a=c=0 → all corners share x).
        ((0, 0, 100, 100), (0.0, 1.0, 0.0, 1.0, 0.0, 0.0)),
        # Matrix collapses y extent (b=d=0 → all corners share y).
        ((0, 0, 100, 100), (1.0, 0.0, 1.0, 0.0, 0.0, 0.0)),
        # Fully singular matrix → point.
        ((0, 0, 100, 100), (0.0, 0.0, 0.0, 0.0, 5.0, 5.0)),
    ],
    ids=[
        "zero_width_bbox",
        "zero_height_bbox",
        "matrix_collapses_x",
        "matrix_collapses_y",
        "singular_matrix",
    ],
)
def test_degenerate_transformed_box_skips_without_error(
    bbox: tuple, matrix: tuple
) -> None:
    r, captured = _make_renderer()
    annot = _FakeAnnotation((0, 0, 100, 100), _FakeAppearance(bbox, matrix))
    # Must not raise ZeroDivisionError; must skip (no CTM captured).
    r._render_annotation(annot)
    assert captured == []


@pytest.mark.parametrize(
    "rect",
    [
        (0, 0, 0, 100),  # zero-width rect
        (0, 0, 100, 0),  # zero-height rect
        (100, 100, 50, 200),  # negative width (llx > urx)
        (100, 100, 200, 50),  # negative height (lly > ury)
        (50, 50, 50, 50),  # zero-area point rect
    ],
    ids=[
        "zero_width_rect",
        "zero_height_rect",
        "negative_width_rect",
        "negative_height_rect",
        "point_rect",
    ],
)
def test_degenerate_rect_skips_without_error(rect: tuple) -> None:
    r, captured = _make_renderer()
    annot = _FakeAnnotation(rect, _FakeAppearance((0, 0, 100, 100), _IDENT_M))
    r._render_annotation(annot)
    assert captured == []


# ----------------------------------------------------------------------
# Visibility flags short-circuit before any appearance work.
# ----------------------------------------------------------------------


def test_hidden_annotation_is_skipped() -> None:
    r, captured = _make_renderer()
    annot = _FakeAnnotation(
        (0, 0, 100, 100), _FakeAppearance((0, 0, 100, 100), _IDENT_M), hidden=True
    )
    r._render_annotation(annot)
    assert captured == []


def test_no_view_annotation_skipped_for_view_destination() -> None:
    r, captured = _make_renderer()
    r._active_destination = "View"
    annot = _FakeAnnotation(
        (0, 0, 100, 100), _FakeAppearance((0, 0, 100, 100), _IDENT_M), no_view=True
    )
    r._render_annotation(annot)
    assert captured == []


def test_no_view_annotation_paints_for_print_destination() -> None:
    """NoView only suppresses View / Export destinations — a Print
    destination must still paint the annotation."""
    r, captured = _make_renderer()
    r._active_destination = "Print"
    annot = _FakeAnnotation(
        (0, 0, 100, 100), _FakeAppearance((0, 0, 100, 100), _IDENT_M), no_view=True
    )
    r._render_annotation(annot)
    assert len(captured) == 1


def test_visible_annotation_paints() -> None:
    r, captured = _make_renderer()
    annot = _FakeAnnotation(
        (0, 0, 100, 100), _FakeAppearance((0, 0, 100, 100), _IDENT_M)
    )
    r._render_annotation(annot)
    assert len(captured) == 1


# ----------------------------------------------------------------------
# Missing-pieces short-circuits (no appearance / no bbox / no rect).
# ----------------------------------------------------------------------


def test_annotation_without_appearance_is_skipped() -> None:
    r, captured = _make_renderer()
    annot = _FakeAnnotation((0, 0, 100, 100), None)
    r._render_annotation(annot)
    assert captured == []


def test_missing_matrix_defaults_to_identity() -> None:
    """A ``/Matrix``-less appearance is treated as identity — the
    composed CTM must equal the pure rect-mapping (S + T)."""
    bbox = (0, 0, 100, 100)
    rect = (10, 20, 110, 220)  # 100 x 200
    r, captured = _make_renderer()
    annot = _FakeAnnotation(rect, _FakeAppearance(bbox, None))
    r._render_annotation(annot)
    assert len(captured) == 1
    expected = _reference_appearance_ctm(bbox, _IDENT_M, rect)
    assert expected is not None
    _assert_matrix_close(captured[0], expected)


def test_short_matrix_defaults_to_identity() -> None:
    """A malformed (< 6 element) ``/Matrix`` falls back to identity
    rather than raising."""
    bbox = (0, 0, 100, 100)
    rect = (0, 0, 100, 100)
    r, captured = _make_renderer()
    appearance = _FakeAppearance(bbox, (1.0, 0.0, 0.0))  # too short
    r._render_annotation(_FakeAnnotation(rect, appearance))
    assert len(captured) == 1
    expected = _reference_appearance_ctm(bbox, _IDENT_M, rect)
    assert expected is not None
    _assert_matrix_close(captured[0], expected)


# ----------------------------------------------------------------------
# CTM is concatenated onto the page CTM, not assigned absolutely.
# ----------------------------------------------------------------------


def test_appearance_ctm_concatenates_onto_existing_page_ctm() -> None:
    """The appearance transform must be *concatenated* onto the current
    page CTM (``_matmul(aa, page_ctm)``), so a non-identity page CTM
    carries through."""
    page_ctm = (1.0, 0.0, 0.0, 1.0, 1000.0, 2000.0)  # page translate
    r, captured = _make_renderer()
    r._gs_stack[0].ctm = page_ctm
    bbox = (0, 0, 100, 100)
    rect = (0, 0, 100, 100)
    r._render_annotation(_FakeAnnotation(rect, _FakeAppearance(bbox, _IDENT_M)))
    assert len(captured) == 1
    aa = _reference_appearance_ctm(bbox, _IDENT_M, rect)
    assert aa is not None
    expected = _matmul(aa, page_ctm)
    _assert_matrix_close(captured[0], expected)


def test_no_rotate_on_rotated_page_applies_counter_rotation() -> None:
    """A NoRotate annotation on a ``/Rotate 90`` page must fold the
    counter-rotation onto the appearance transform; the composed CTM
    differs from the same annotation without the NoRotate flag."""
    bbox = (0, 0, 100, 100)
    rect = (0, 0, 100, 100)
    r_plain, cap_plain = _make_renderer(page_rotation=90)
    r_plain._render_annotation(
        _FakeAnnotation(rect, _FakeAppearance(bbox, _IDENT_M), no_rotate=False)
    )
    r_nr, cap_nr = _make_renderer(page_rotation=90)
    r_nr._render_annotation(
        _FakeAnnotation(rect, _FakeAppearance(bbox, _IDENT_M), no_rotate=True)
    )
    assert len(cap_plain) == 1
    assert len(cap_nr) == 1
    # The counter-rotation must actually change the composed transform.
    assert cap_plain[0] != cap_nr[0]


def test_no_rotate_on_unrotated_page_is_noop() -> None:
    """On a ``/Rotate 0`` page the NoRotate counter-rotation is the
    identity, so the flag does not change the composed CTM."""
    bbox = (0, 0, 100, 100)
    rect = (10, 10, 110, 110)
    r_plain, cap_plain = _make_renderer(page_rotation=0)
    r_plain._render_annotation(
        _FakeAnnotation(rect, _FakeAppearance(bbox, _IDENT_M), no_rotate=False)
    )
    r_nr, cap_nr = _make_renderer(page_rotation=0)
    r_nr._render_annotation(
        _FakeAnnotation(rect, _FakeAppearance(bbox, _IDENT_M), no_rotate=True)
    )
    assert len(cap_plain) == 1
    assert len(cap_nr) == 1
    _assert_matrix_close(cap_nr[0], cap_plain[0])
