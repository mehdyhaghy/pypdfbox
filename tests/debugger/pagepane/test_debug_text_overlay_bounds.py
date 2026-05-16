"""Tests for :func:`transform` and :func:`calculate_glyph_bounds`.

These two helpers were ported from upstream
``DebugTextOverlay.DebugTextStripper.transform`` /
``DebugTextOverlay.DebugTextStripper.calculateGlyphBounds`` (PDFBox 3.0).
The pypdfbox port models a Java ``AffineTransform`` as the 6-float tuple
``(sx, hy, hx, sy, tx, ty)`` (the same shape :meth:`Matrix.create_affine_transform`
returns) and a ``Shape`` as a list of ``(x, y)`` corner points (matching
:meth:`PDRectangle.to_general_path`).
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from pypdfbox.debugger.pagepane.debug_text_overlay import (
    _bounds2d,
    _concatenate_at,
    calculate_glyph_bounds,
    transform,
)

# ---------------------------------------------------------------------------
# transform()
# ---------------------------------------------------------------------------


_UNIT_SQUARE: list[tuple[float, float]] = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def _approx_points(
    actual: list[tuple[float, float]],
    expected: list[tuple[float, float]],
    *,
    atol: float = 1e-9,
) -> None:
    assert len(actual) == len(expected)
    for (ax, ay), (ex, ey) in zip(actual, expected, strict=True):
        assert ax == pytest.approx(ex, abs=atol)
        assert ay == pytest.approx(ey, abs=atol)


def test_transform_identity_is_a_no_op() -> None:
    at = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    result = transform(_UNIT_SQUARE, at)
    _approx_points(result, _UNIT_SQUARE)


def test_transform_translate_offsets_every_point() -> None:
    at = (1.0, 0.0, 0.0, 1.0, 10.0, 20.0)
    result = transform(_UNIT_SQUARE, at)
    _approx_points(
        result,
        [(10.0, 20.0), (11.0, 20.0), (11.0, 21.0), (10.0, 21.0)],
    )


def test_transform_scale_stretches_each_axis() -> None:
    at = (3.0, 0.0, 0.0, 4.0, 0.0, 0.0)
    result = transform(_UNIT_SQUARE, at)
    _approx_points(
        result,
        [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0), (0.0, 4.0)],
    )


def test_transform_rotate_90deg_ccw() -> None:
    # 90 deg counter-clockwise around the origin: (x, y) -> (-y, x).
    theta = math.pi / 2.0
    c = math.cos(theta)
    s = math.sin(theta)
    at = (c, s, -s, c, 0.0, 0.0)
    result = transform(_UNIT_SQUARE, at)
    _approx_points(
        result,
        [(0.0, 0.0), (0.0, 1.0), (-1.0, 1.0), (-1.0, 0.0)],
        atol=1e-9,
    )


def test_transform_does_not_mutate_input() -> None:
    pts = list(_UNIT_SQUARE)
    transform(pts, (2.0, 0.0, 0.0, 2.0, 0.0, 0.0))
    assert pts == _UNIT_SQUARE


def test_transform_accepts_empty_shape() -> None:
    assert transform([], (1.0, 0.0, 0.0, 1.0, 5.0, 5.0)) == []


# ---------------------------------------------------------------------------
# _concatenate_at()  /  _bounds2d() — internals used by calculate_glyph_bounds
# ---------------------------------------------------------------------------


def test_concatenate_at_translate_after_scale() -> None:
    # Java semantics: at.concatenate(b)  ==>  apply b first, then at.
    # Build: scale 2x  then  translate (10, 20)  ==>  for input (1, 1):
    #   first translate to (11, 21), then scale to (22, 42).
    scale = (2.0, 0.0, 0.0, 2.0, 0.0, 0.0)
    trans = (1.0, 0.0, 0.0, 1.0, 10.0, 20.0)
    combined = _concatenate_at(scale, trans)
    out = transform([(1.0, 1.0)], combined)
    _approx_points(out, [(22.0, 42.0)])


def test_bounds2d_returns_axis_aligned_envelope() -> None:
    pts = [(0.0, 0.0), (3.0, -1.0), (-2.0, 5.0), (4.0, 2.0)]
    assert _bounds2d(pts) == (-2.0, -1.0, 4.0, 5.0)


# ---------------------------------------------------------------------------
# calculate_glyph_bounds() — non-Type3 path with stub font
# ---------------------------------------------------------------------------


class _StubBBox:
    """``PDRectangle``-shaped duck for a font bounding box."""

    def __init__(
        self,
        llx: float = -100.0,
        lly: float = -200.0,
        urx: float = 900.0,
        ury: float = 800.0,
    ) -> None:
        self.llx, self.lly, self.urx, self.ury = llx, lly, urx, ury

    def get_lower_left_x(self) -> float:
        return self.llx

    def get_lower_left_y(self) -> float:
        return self.lly

    def get_upper_right_x(self) -> float:
        return self.urx

    def get_upper_right_y(self) -> float:
        return self.ury


class _StubFont:
    """Minimal non-Type3 font with a bbox + a standard 1/1000-em font matrix."""

    def __init__(
        self,
        bbox: _StubBBox | None = None,
        font_matrix: list[float] | None = None,
    ) -> None:
        self._bbox = bbox if bbox is not None else _StubBBox()
        self._font_matrix = (
            list(font_matrix)
            if font_matrix is not None
            else [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]
        )

    def get_bounding_box(self) -> _StubBBox | None:
        return self._bbox

    def get_font_matrix(self) -> list[float]:
        return list(self._font_matrix)

    def is_embedded(self) -> bool:
        return True

    def is_vertical(self) -> bool:
        return False

    def is_standard14(self) -> bool:
        return False

    def has_explicit_width(self, _code: int) -> bool:
        return False


def test_calculate_glyph_bounds_returns_none_when_font_none() -> None:
    assert calculate_glyph_bounds(
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), None, 65, None
    ) is None


def test_calculate_glyph_bounds_returns_none_when_font_has_no_bbox() -> None:
    class _NoBBoxFont(_StubFont):
        def get_bounding_box(self) -> None:
            return None

    assert (
        calculate_glyph_bounds(
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), _NoBBoxFont(), 65, None
        )
        is None
    )


def test_calculate_glyph_bounds_swallows_bbox_oserror() -> None:
    class _BoomFont(_StubFont):
        def get_bounding_box(self) -> None:
            raise OSError("font file gone")

    assert (
        calculate_glyph_bounds(
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), _BoomFont(), 65, None
        )
        is None
    )


def test_calculate_glyph_bounds_identity_at_returns_glyph_space_bbox() -> None:
    """With AT=identity and the default 1/1000-em font matrix, the four
    corners come back scaled by 1/1000 from the font's bbox.
    """
    bbox = _StubBBox(llx=0.0, lly=0.0, urx=1000.0, ury=500.0)
    font = _StubFont(bbox=bbox)

    pts = calculate_glyph_bounds(
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), font, 65, None
    )
    assert pts is not None
    # Expect a unit-ish quad: 0..1 wide, 0..0.5 tall.
    _approx_points(
        pts,
        [(0.0, 0.0), (1.0, 0.0), (1.0, 0.5), (0.0, 0.5)],
        atol=1e-9,
    )


def test_calculate_glyph_bounds_applies_text_rendering_matrix() -> None:
    """A 12-pt text rendering matrix at origin (50, 100) should translate
    and scale the resulting quad accordingly.
    """
    bbox = _StubBBox(llx=0.0, lly=0.0, urx=1000.0, ury=1000.0)
    font = _StubFont(bbox=bbox)
    # Text rendering matrix: 12pt at (50, 100). After concatenation with
    # the 1/1000-em font matrix the effective scale becomes 12/1000 = 0.012.
    at = (12.0, 0.0, 0.0, 12.0, 50.0, 100.0)

    pts = calculate_glyph_bounds(at, font, 65, None)
    assert pts is not None
    _approx_points(
        pts,
        [(50.0, 100.0), (62.0, 100.0), (62.0, 112.0), (50.0, 112.0)],
        atol=1e-9,
    )


def test_calculate_glyph_bounds_prefers_normalized_path_when_tighter() -> None:
    """When ``get_normalized_path`` returns a usable point list, the helper
    should bbox *that* path rather than the looser font-wide bbox.
    """

    class _PathFont(_StubFont):
        def __init__(self) -> None:
            # Loose bbox so we can tell the path was used instead.
            super().__init__(_StubBBox(-500.0, -500.0, 1500.0, 1500.0))

        def get_normalized_path(self, _code: int) -> list[tuple[float, float]]:
            # A small triangle inside the loose bbox.
            return [(0.0, 0.0), (200.0, 0.0), (100.0, 300.0)]

    at = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    pts = calculate_glyph_bounds(at, _PathFont(), 65, None)
    assert pts is not None
    # Path bbox is (0, 0)..(200, 300); under 1/1000-em font matrix:
    _approx_points(
        pts,
        [(0.0, 0.0), (0.2, 0.0), (0.2, 0.3), (0.0, 0.3)],
        atol=1e-9,
    )


def test_calculate_glyph_bounds_falls_back_when_normalized_path_unusable() -> None:
    """If ``get_normalized_path`` returns ``None`` the bbox path is used."""

    class _NullPathFont(_StubFont):
        def get_normalized_path(self, _code: int) -> None:
            return None

    bbox = _StubBBox(llx=0.0, lly=0.0, urx=1000.0, ury=1000.0)
    font = _NullPathFont(bbox=bbox)
    pts = calculate_glyph_bounds((1.0, 0.0, 0.0, 1.0, 0.0, 0.0), font, 65, None)
    assert pts is not None
    _approx_points(
        pts,
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        atol=1e-9,
    )


def test_calculate_glyph_bounds_stretches_non_embedded_explicit_width() -> None:
    """A non-embedded standard font with a mismatched explicit width should
    have its x-axis scaled by ``pdf_width / font_width`` (PDFBOX-3450 fix).
    """

    class _Disp:
        def get_x(self) -> float:
            return 0.5  # pdf width = 500

    class _StretchFont(_StubFont):
        def is_embedded(self) -> bool:
            return False

        def has_explicit_width(self, _code: int) -> bool:
            return True

        def get_width_from_font(self, _code: int) -> float:
            return 1000.0  # font width = 1000 — half the pdf width's inverse

    bbox = _StubBBox(llx=0.0, lly=0.0, urx=1000.0, ury=1000.0)
    font = _StretchFont(bbox=bbox)
    pts = calculate_glyph_bounds(
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), font, 65, _Disp()
    )
    assert pts is not None
    # x range is squashed by 500/1000 = 0.5; y unchanged.
    llx, lly, urx, ury = _bounds2d(pts)
    assert urx - llx == pytest.approx(0.5, abs=1e-9)
    assert ury - lly == pytest.approx(1.0, abs=1e-9)


# ---------------------------------------------------------------------------
# calculate_glyph_bounds() — Type3 path
# ---------------------------------------------------------------------------


def test_calculate_glyph_bounds_type3_uses_char_proc_glyph_bbox() -> None:
    """For ``PDType3Font`` the helper takes the per-glyph bbox from the
    char-proc instead of the font-wide bbox.
    """
    from pypdfbox.cos.cos_array import COSArray
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_float import COSFloat
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font
    from pypdfbox.pdmodel.pd_rectangle import PDRectangle

    # Build a real PDType3Font with a /FontBBox and a stand-in char proc
    # whose glyph bbox we control.
    font_dict = COSDictionary()
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    font_dict.set_item(
        COSName.get_pdf_name("FontBBox"),
        PDRectangle(0.0, 0.0, 100.0, 100.0).to_cos_array(),
    )
    font_dict.set_item(
        COSName.get_pdf_name("FontMatrix"),
        COSArray([
            COSFloat(0.01),
            COSFloat(0.0),
            COSFloat(0.0),
            COSFloat(0.01),
            COSFloat(0.0),
            COSFloat(0.0),
        ]),
    )
    font = PDType3Font(font_dict)

    class _CharProc:
        def get_glyph_bbox(self) -> PDRectangle:
            return PDRectangle(10.0, 10.0, 50.0, 80.0)

    # Monkey-patch the lookup to return our stub char proc regardless of
    # /Encoding / /CharProcs plumbing (orthogonal to what we want to test).
    font.get_char_proc = lambda _code: _CharProc()  # type: ignore[assignment]

    pts = calculate_glyph_bounds(
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), font, 65, None
    )
    assert pts is not None
    # Glyph bbox (10..50, 10..80) under font matrix scale 0.01. We use a
    # loose tolerance because ``COSFloat`` round-trips through float32 and
    # 0.01 isn't exactly representable.
    _approx_points(
        pts,
        [(0.1, 0.1), (0.5, 0.1), (0.5, 0.8), (0.1, 0.8)],
        atol=1e-6,
    )


def test_calculate_glyph_bounds_type3_returns_none_when_no_char_proc() -> None:
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

    font_dict = COSDictionary()
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    font = PDType3Font(font_dict)
    font.get_char_proc = lambda _code: None  # type: ignore[assignment]

    assert (
        calculate_glyph_bounds(
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), font, 99, None
        )
        is None
    )


def test_calculate_glyph_bounds_type3_returns_none_when_glyph_bbox_none() -> None:
    from pypdfbox.cos.cos_dictionary import COSDictionary
    from pypdfbox.cos.cos_name import COSName
    from pypdfbox.pdmodel.font.pd_type3_font import PDType3Font

    class _CharProc:
        def get_glyph_bbox(self) -> None:
            return None

    font_dict = COSDictionary()
    font_dict.set_item(COSName.SUBTYPE, COSName.get_pdf_name("Type3"))
    font = PDType3Font(font_dict)
    font.get_char_proc = lambda _code: _CharProc()  # type: ignore[assignment]

    assert (
        calculate_glyph_bounds(
            (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), font, 99, None
        )
        is None
    )


# ---------------------------------------------------------------------------
# calculate_glyph_bounds() — real bundled font (Liberation Sans Regular)
# ---------------------------------------------------------------------------


_LIBERATION_SANS = (
    Path(__file__).resolve().parents[3]
    / "pypdfbox"
    / "resources"
    / "ttf"
    / "LiberationSans-Regular.ttf"
)


def _liberation_sans_bbox() -> _StubBBox:
    """Read the head table directly with fontTools so we don't depend on
    the (still-evolving) ``PDTrueTypeFont`` loader surface in the parity
    matrix.
    """
    from fontTools.ttLib import TTFont

    tt = TTFont(str(_LIBERATION_SANS))
    head = tt["head"]
    units = head.unitsPerEm
    # Glyph-space coords on the standard 1000-em scale.
    scale = 1000.0 / units
    return _StubBBox(
        llx=head.xMin * scale,
        lly=head.yMin * scale,
        urx=head.xMax * scale,
        ury=head.yMax * scale,
    )


def test_calculate_glyph_bounds_with_real_font_bbox_lands_near_origin() -> None:
    """With a Liberation Sans bounding box (~1000-em normalised), a 12pt
    text rendering matrix at (50, 100) yields a quad whose corners fall
    within a few text-points of the expected envelope.
    """
    if not _LIBERATION_SANS.exists():  # pragma: no cover - resource missing
        pytest.skip("Liberation Sans TTF not bundled")

    font = _StubFont(bbox=_liberation_sans_bbox())
    at = (12.0, 0.0, 0.0, 12.0, 50.0, 100.0)

    pts = calculate_glyph_bounds(at, font, ord("A"), None)
    assert pts is not None
    llx, lly, urx, ury = _bounds2d(pts)

    # Liberation Sans head bbox at 12pt: width ~ a couple of em; ensure
    # the result is anchored near the rendering origin (50, 100) and the
    # quad spans something believable.
    assert 30.0 < llx < 60.0
    assert 60.0 < lly < 100.0
    assert 60.0 < urx < 100.0
    assert 110.0 < ury < 130.0


# ---------------------------------------------------------------------------
# Signature-shape parity with upstream
# ---------------------------------------------------------------------------


def test_calculate_glyph_bounds_signature_matches_upstream() -> None:
    """Parameter order: (at, font, code, displacement) — exact upstream order."""
    import inspect

    sig = inspect.signature(calculate_glyph_bounds)
    assert list(sig.parameters) == ["at", "font", "code", "displacement"]


def test_transform_signature_matches_upstream() -> None:
    """Parameter order: (shape, at) — matches upstream
    ``AffineTransform.createTransformedShape(shape)`` call shape with the
    transform as the second positional argument.
    """
    import inspect

    sig = inspect.signature(transform)
    params = list(sig.parameters)
    assert params == ["shape", "at"]


def test_calculate_glyph_bounds_accepts_dict_font_matrix_default() -> None:
    """If ``get_font_matrix`` raises ``AttributeError``, the helper should
    fall back to the identity matrix and still produce a result.
    """

    class _NoMatrixFont(_StubFont):
        def get_font_matrix(self) -> list[float]:  # type: ignore[override]
            raise AttributeError("no matrix")

    pts = calculate_glyph_bounds(
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        _NoMatrixFont(_StubBBox(0.0, 0.0, 10.0, 10.0)),
        65,
        None,
    )
    assert pts is not None
    # Identity font matrix => coords flow through unscaled.
    _approx_points(
        pts,
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)],
        atol=1e-9,
    )


def test_calculate_glyph_bounds_handles_displacement_missing_get_x() -> None:
    """A non-embedded explicit-width font with a malformed ``displacement``
    (no ``get_x``) should not crash — the stretch step is skipped.
    """

    class _StretchFont(_StubFont):
        def is_embedded(self) -> bool:
            return False

        def has_explicit_width(self, _code: int) -> bool:
            return True

        def get_width_from_font(self, _code: int) -> float:
            return 1000.0

    pts = calculate_glyph_bounds(
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0),
        _StretchFont(_StubBBox(0.0, 0.0, 1000.0, 1000.0)),
        65,
        object(),  # has no ``get_x``
    )
    # The result should still be the un-stretched bbox.
    assert pts is not None
    _approx_points(
        pts,
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        atol=1e-9,
    )


def test_calculate_glyph_bounds_handles_introspection_attribute_errors() -> None:
    """A font missing ``is_embedded`` / ``is_vertical`` / ``is_standard14`` /
    ``has_explicit_width`` should silently skip the stretch branch.
    """

    class _BareFont:
        def get_bounding_box(self) -> _StubBBox:
            return _StubBBox(0.0, 0.0, 1000.0, 1000.0)

        def get_font_matrix(self) -> list[float]:
            return [0.001, 0.0, 0.0, 0.001, 0.0, 0.0]

    pts = calculate_glyph_bounds(
        (1.0, 0.0, 0.0, 1.0, 0.0, 0.0), _BareFont(), 65, None
    )
    assert pts is not None
    _approx_points(
        pts,
        [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
        atol=1e-9,
    )
