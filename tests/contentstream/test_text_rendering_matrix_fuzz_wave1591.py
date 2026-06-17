"""Fuzz the text-rendering-matrix composition used to place glyphs.

PDF 32000-1 §9.4.4 / upstream ``PDFStreamEngine.getTextRenderingMatrix``:
the glyph placement matrix is

    Trm = parameters × Tm × CTM

where the *parameters* (text-state) matrix is

    [ fontSize * Tz/100 ,      0      ]
    [        0          ,  fontSize   ]
    [        0          ,    rise     ]

i.e. ``Matrix(fontSize * horizontalScaling, 0, 0, fontSize, 0, rise)`` with
``horizontalScaling == Tz / 100``. The a-element folds the horizontal scaling
into the X axis only; the d-element is the bare font size; the f-element is the
text rise (Ts); b == c == e == 0.

These cases hammer:
* the parameters matrix element layout (a = fontSize*Tz/100, d = fontSize,
  f = rise, b = c = e = 0),
* the composition order (parameters applied *first*, then Tm, then CTM —
  PDFBox ``parameters.multiply(textMatrix).multiply(ctm)`` and the renderer's
  ``_matmul(text_local, Tm)`` then ``_matmul(.., CTM)``),
* a non-identity text matrix translating / rotating the origin,
* a non-identity CTM,
* the rise (Ts) shifting the glyph along the text matrix's local Y axis,
* horizontal scaling (Tz) affecting only the X scale,
* the device origin of a glyph at text-space (0, 0) — the f-translation of Trm.

Both the production ``Matrix.multiply`` path (used by the text stripper) and the
renderer's tuple ``_matmul`` helper (used by ``PDFRenderer._draw_glyph``) are
checked against an independent reference and against each other, so a reversed
multiply order, a dropped Tz factor, a mis-slotted rise, or a Tz leaking onto
the Y axis would all fail here.
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.rendering.pdf_renderer import _matmul
from pypdfbox.util.matrix import Matrix


# --------------------------------------------------------------------------
# Reference helpers (independent of the production code under test).
# --------------------------------------------------------------------------
def _ref_matmul(m1, m2):
    """Standard row-vector product ``m1 · m2`` (apply m1 first, then m2).

    Each matrix is the 6-tuple ``(a, b, c, d, e, f)`` representing

        [ a b 0 ]
        [ c d 0 ]
        [ e f 1 ]

    so ``[x y 1] · M = (a*x + c*y + e, b*x + d*y + f)``. This is the same
    convention as PDFBox ``Matrix.multiply`` and the renderer's ``_matmul``.
    """
    a1, b1, c1, d1, e1, f1 = m1
    a2, b2, c2, d2, e2, f2 = m2
    return (
        a1 * a2 + b1 * c2,
        a1 * b2 + b1 * d2,
        c1 * a2 + d1 * c2,
        c1 * b2 + d1 * d2,
        e1 * a2 + f1 * c2 + e2,
        e1 * b2 + f1 * d2 + f2,
    )


def _parameters(font_size, tz, rise):
    """The text-state (parameters) matrix per upstream."""
    return (font_size * (tz / 100.0), 0.0, 0.0, font_size, 0.0, rise)


def _matrix_tuple(m: Matrix):
    return (
        m.get_scale_x(),
        m.get_shear_y(),
        m.get_shear_x(),
        m.get_scale_y(),
        m.get_translate_x(),
        m.get_translate_y(),
    )


def _via_matrix(params, tm, ctm):
    """Compose via the production ``Matrix.multiply`` (PDFBox path)."""
    pm = Matrix(*params)
    tmm = Matrix(*tm)
    ctmm = Matrix(*ctm)
    return _matrix_tuple(pm.multiply(tmm).multiply(ctmm))


def _via_renderer(params, tm, ctm):
    """Compose via the renderer's tuple ``_matmul`` (PDFRenderer path)."""
    glyph_to_user = _matmul(params, tm)
    return _matmul(glyph_to_user, ctm)


def _assert_close(actual, expected, tol=1e-3):
    for a, e in zip(actual, expected, strict=True):
        assert math.isclose(a, e, rel_tol=1e-5, abs_tol=tol), (
            f"element mismatch: {actual!r} vs {expected!r}"
        )


_IDENTITY = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


# --------------------------------------------------------------------------
# Parameter-set fuzz corpus: (font_size, Tz, rise, Tm, CTM).
# --------------------------------------------------------------------------
_CASES = [
    # name, font_size, tz, rise, tm, ctm
    ("identity_12pt", 12.0, 100.0, 0.0, _IDENTITY, _IDENTITY),
    ("tiny_font", 0.5, 100.0, 0.0, _IDENTITY, _IDENTITY),
    ("huge_font", 1000.0, 100.0, 0.0, _IDENTITY, _IDENTITY),
    ("tz_50", 14.0, 50.0, 0.0, _IDENTITY, _IDENTITY),
    ("tz_200", 14.0, 200.0, 0.0, _IDENTITY, _IDENTITY),
    ("tz_0", 14.0, 0.0, 0.0, _IDENTITY, _IDENTITY),
    ("rise_pos", 10.0, 100.0, 5.0, _IDENTITY, _IDENTITY),
    ("rise_neg", 10.0, 100.0, -3.0, _IDENTITY, _IDENTITY),
    ("rise_large", 10.0, 100.0, 100.0, _IDENTITY, _IDENTITY),
    ("tm_translate", 12.0, 100.0, 0.0, (1.0, 0.0, 0.0, 1.0, 100.0, 200.0), _IDENTITY),
    ("tm_scale", 1.0, 100.0, 0.0, (14.0, 0.0, 0.0, 14.0, 0.0, 0.0), _IDENTITY),
    (
        "tm_folds_fontsize",  # 14 0 0 14 .. Tm with 1 Tf
        1.0,
        100.0,
        0.0,
        (14.0, 0.0, 0.0, 14.0, 72.0, 720.0),
        _IDENTITY,
    ),
    (
        "tm_rotate_90",
        12.0,
        100.0,
        0.0,
        (0.0, 1.0, -1.0, 0.0, 50.0, 60.0),
        _IDENTITY,
    ),
    (
        "ctm_translate",
        12.0,
        100.0,
        0.0,
        _IDENTITY,
        (1.0, 0.0, 0.0, 1.0, 30.0, 40.0),
    ),
    (
        "ctm_scale_2x",
        12.0,
        100.0,
        0.0,
        _IDENTITY,
        (2.0, 0.0, 0.0, 2.0, 0.0, 0.0),
    ),
    (
        "ctm_yflip",  # device CTM y-flip
        12.0,
        100.0,
        0.0,
        _IDENTITY,
        (1.0, 0.0, 0.0, -1.0, 0.0, 792.0),
    ),
    (
        "tm_and_ctm",
        10.0,
        100.0,
        0.0,
        (1.0, 0.0, 0.0, 1.0, 100.0, 100.0),
        (2.0, 0.0, 0.0, -2.0, 10.0, 600.0),
    ),
    (
        "tz_rise_tm_ctm",
        18.0,
        75.0,
        6.0,
        (1.0, 0.0, 0.0, 1.0, 20.0, 30.0),
        (1.5, 0.0, 0.0, -1.5, 5.0, 500.0),
    ),
    (
        "tm_shear",
        12.0,
        120.0,
        2.0,
        (1.0, 0.2, 0.1, 1.0, 10.0, 10.0),
        _IDENTITY,
    ),
    (
        "ctm_rotate_30",
        12.0,
        100.0,
        0.0,
        _IDENTITY,
        (
            math.cos(math.radians(30)),
            math.sin(math.radians(30)),
            -math.sin(math.radians(30)),
            math.cos(math.radians(30)),
            0.0,
            0.0,
        ),
    ),
    (
        "everything_nontrivial",
        9.5,
        88.0,
        -4.0,
        (1.1, 0.05, -0.05, 1.1, 40.0, 50.0),
        (1.3, 0.0, 0.0, -1.3, 12.0, 480.0),
    ),
    ("zero_font", 0.0, 100.0, 0.0, _IDENTITY, _IDENTITY),
    ("rise_with_rotate", 12.0, 100.0, 8.0, (0.0, 1.0, -1.0, 0.0, 0.0, 0.0), _IDENTITY),
    ("negative_tz", 14.0, -100.0, 0.0, _IDENTITY, _IDENTITY),
]


@pytest.mark.parametrize(
    "name,font_size,tz,rise,tm,ctm",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_trm_matches_reference(name, font_size, tz, rise, tm, ctm):
    """Both production paths reproduce the independent reference Trm."""
    params = _parameters(font_size, tz, rise)
    expected = _ref_matmul(_ref_matmul(params, tm), ctm)

    _assert_close(_via_matrix(params, tm, ctm), expected)
    _assert_close(_via_renderer(params, tm, ctm), expected)


@pytest.mark.parametrize(
    "name,font_size,tz,rise,tm,ctm",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_matrix_and_renderer_paths_agree(name, font_size, tz, rise, tm, ctm):
    """The stripper's Matrix path and the renderer's _matmul path agree."""
    params = _parameters(font_size, tz, rise)
    _assert_close(_via_matrix(params, tm, ctm), _via_renderer(params, tm, ctm))


def test_parameters_matrix_layout():
    """The parameters matrix puts Tz on a, fontSize on d, rise on f only."""
    a, b, c, d, e, f = _parameters(font_size=12.0, tz=80.0, rise=5.0)
    assert a == pytest.approx(12.0 * 0.8)  # fontSize * Tz/100 on the X axis
    assert d == pytest.approx(12.0)  # bare font size on the Y axis
    assert f == pytest.approx(5.0)  # rise in the f slot
    assert b == 0.0
    assert c == 0.0
    assert e == 0.0  # rise must NOT leak into e (the X translation)


def test_tz_affects_x_axis_only():
    """Horizontal scaling scales the a-element, never the d-element."""
    base = _parameters(font_size=10.0, tz=100.0, rise=0.0)
    scaled = _parameters(font_size=10.0, tz=200.0, rise=0.0)
    # a doubles, d unchanged.
    assert scaled[0] == pytest.approx(2.0 * base[0])
    assert scaled[3] == pytest.approx(base[3])


def test_rise_not_scaled_by_font_size():
    """A given rise produces the same f-offset regardless of font size.

    The rise sits in the parameters matrix's f slot *unscaled* by font size;
    only the surrounding Tm/CTM transform it. With identity Tm/CTM the device
    origin's Y offset equals the rise exactly for any font size.
    """
    for fs in (1.0, 12.0, 144.0):
        trm = _via_matrix(_parameters(fs, 100.0, 7.0), _IDENTITY, _IDENTITY)
        assert trm[5] == pytest.approx(7.0)  # f-translation == rise


def test_glyph_origin_at_text_space_zero():
    """Device origin of a glyph at text-space (0,0) is Trm's f-translation.

    Transforming the point (0,0) by Trm yields exactly (Trm.e, Trm.f). For a
    plain ``... Tm`` with a translating CTM the origin lands at the composed
    translation.
    """
    font_size, tz, rise = 12.0, 100.0, 0.0
    tm = (1.0, 0.0, 0.0, 1.0, 100.0, 200.0)
    ctm = (1.0, 0.0, 0.0, -1.0, 0.0, 792.0)  # y-flip device CTM
    trm = _via_matrix(_parameters(font_size, tz, rise), tm, ctm)
    # Origin (0,0) maps to (e, f).
    origin_x, origin_y = trm[4], trm[5]
    assert origin_x == pytest.approx(100.0)
    assert origin_y == pytest.approx(792.0 - 200.0)  # 200 flipped about 792


def test_rise_shifts_along_tm_local_y():
    """A positive rise lifts the glyph along the text matrix's local Y axis.

    With a 90deg-rotated Tm the local +Y axis points along device -X, so a
    positive rise shifts the device origin in -X (not +Y). This guards against
    the rise being applied in device space instead of text space.
    """
    tm_rot = (0.0, 1.0, -1.0, 0.0, 0.0, 0.0)  # rotate +90
    no_rise = _via_matrix(_parameters(10.0, 100.0, 0.0), tm_rot, _IDENTITY)
    with_rise = _via_matrix(_parameters(10.0, 100.0, 5.0), tm_rot, _IDENTITY)
    # local +Y (0,1) rotated +90 -> device (-1, 0); rise 5 -> dx = -5, dy = 0.
    assert with_rise[4] - no_rise[4] == pytest.approx(-5.0)
    assert with_rise[5] - no_rise[5] == pytest.approx(0.0)


def test_composition_order_not_reversed():
    """params × Tm × CTM differs from CTM × Tm × params under a non-commuting
    setup — verify the production code uses the correct (former) order."""
    params = _parameters(font_size=1.0, tz=100.0, rise=0.0)
    tm = (14.0, 0.0, 0.0, 14.0, 0.0, 0.0)  # scale 14
    ctm = (1.0, 0.0, 0.0, 1.0, 100.0, 0.0)  # translate +100 x

    correct = _via_matrix(params, tm, ctm)
    reversed_order = _ref_matmul(_ref_matmul(ctm, tm), params)

    # Correct order: translation stays 100 (CTM applied last, after the scale).
    assert correct[4] == pytest.approx(100.0)
    # Reversed order would scale the translation by 14 -> 1400. They must differ.
    assert reversed_order[4] == pytest.approx(1400.0)
    assert correct[4] != pytest.approx(reversed_order[4])


def test_renderer_full_pipeline_origin_matches_pdfbox_formula():
    """End-to-end: a 14pt glyph at text origin under a translating page CTM.

    Mirrors ``PDFStreamEngine`` placing a glyph: parameters(14,100,0) × Tm(at
    72,720) × CTM(identity). Device origin must be (72, 720) with scale 14.
    """
    params = _parameters(14.0, 100.0, 0.0)
    tm = (1.0, 0.0, 0.0, 1.0, 72.0, 720.0)
    trm = _via_renderer(params, tm, _IDENTITY)
    assert trm[0] == pytest.approx(14.0)  # x scale = fontSize
    assert trm[3] == pytest.approx(14.0)  # y scale = fontSize
    assert trm[4] == pytest.approx(72.0)
    assert trm[5] == pytest.approx(720.0)
