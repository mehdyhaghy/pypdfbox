"""Bit-identity + cache-invalidation guards for the show-text matrix fast paths.

Wave-3 performance work replaced two per-show-text-run 3x3 matrix multiplies in
:mod:`pypdfbox.text.pdf_text_stripper` with:

* :meth:`PDFTextStripper._scale_and_dir` — a cache of the text-rendering
  matrix's translation-invariant derived values ``(x_scale, y_scale, dir)``,
  dropped whenever ``BT``/``Tm``/``Ts``/``Q``/``cm`` mutate an input.
* :meth:`PDFTextStripper._origin_translate` — a direct computation of the two
  translation cells consumed by every ``_origin_matrix`` caller (no-rise path).

Both must be *bit-for-bit* identical to the full-multiply results they replace,
because glyph positions feed word-gap splitting and sort ordering where a 1-ULP
drift could reorder output. These tests assert exact IEEE-754 identity (via the
raw byte pattern, so ``-0.0``/``+0.0``/``NaN`` are distinguished) and that the
cache is invalidated by exactly the operators that change its inputs.
"""

from __future__ import annotations

import math
import struct

import pytest

from pypdfbox.cos import COSFloat, COSInteger
from pypdfbox.text import PDFTextStripper
from pypdfbox.text.pdf_text_stripper import _TextState
from pypdfbox.util.matrix import Matrix

# A spread of text matrices and CTMs: identity, uniform scale, point-size folded
# into Tm, rotations (90/180/270 and an off-axis angle), shear, and a per-line
# translate CTM. Chosen to exercise both branches of get_scaling_factor_* and
# every quadrant of _text_dir.
_TMS = [
    (1.0, 0.0, 0.0, 1.0),
    (14.0, 0.0, 0.0, 14.0),
    (0.0, 1.0, -1.0, 0.0),  # +90
    (-1.0, 0.0, 0.0, -1.0),  # 180
    (0.0, -1.0, 1.0, 0.0),  # 270
    (0.7071068, 0.7071068, -0.7071068, 0.7071068),  # 45
    (2.0, 0.5, 0.25, 3.0),  # shear
    (0.1, 0.0, 0.0, 0.1),
]
_CTMS = [
    Matrix(),
    Matrix(1.5, 0.0, 0.0, 1.5, 100.0, 200.0),
    Matrix(0.0, 1.0, -1.0, 0.0, 612.0, 0.0),  # page /Rotate 90
    Matrix(0.9950042, 0.09983342, -0.09983342, 0.9950042, 33.3, -7.75),
    Matrix(3.0, 0.0, 0.0, -2.0, 10.0, 792.0),
]
_XY = [
    (0.0, 0.0),
    (10.0, 20.0),
    (123.456, -78.9),
    (1e-4, 1e-4),
    (1000000.0, 0.5),
]


def _bits(value: float) -> bytes:
    return struct.pack(">d", value)


def _make_state(
    tm: tuple[float, float, float, float], ctm: Matrix, rise: float = 0.0
) -> _TextState:
    state = _TextState()
    state.tm_a, state.tm_b, state.tm_c, state.tm_d = tm
    state.ctm = ctm
    state.text_rise = rise
    return state


# --------------------------------------------------------------------------
# _origin_translate: bit-identical to _origin_matrix().get_translate_*()
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tm", _TMS)
@pytest.mark.parametrize("ctm", _CTMS)
@pytest.mark.parametrize("rise", [0.0, 4.0, -3.5])
def test_origin_translate_matches_full_multiply(
    tm: tuple[float, float, float, float], ctm: Matrix, rise: float
) -> None:
    stripper = PDFTextStripper()
    for text_x, text_y in _XY:
        state = _make_state(tm, ctm, rise)
        full = stripper._origin_matrix(state, text_x, text_y)  # noqa: SLF001
        want_x, want_y = full.get_translate_x(), full.get_translate_y()
        got_x, got_y = stripper._origin_translate(  # noqa: SLF001
            state, text_x, text_y
        )
        # Raw byte identity — not just == — so a sign-of-zero drift would fail.
        assert _bits(got_x) == _bits(want_x), (tm, ctm, rise, text_x, text_y)
        assert _bits(got_y) == _bits(want_y), (tm, ctm, rise, text_x, text_y)


def test_origin_translate_non_finite_raises_like_multiply() -> None:
    stripper = PDFTextStripper()
    # A CTM whose translate cell is +inf makes the composed translation
    # non-finite; the full multiply's checkFloatValues raises, and the direct
    # path must raise the identical error.
    ctm = Matrix()
    ctm.set_value(2, 0, math.inf)  # ctm translate-x cell
    state = _make_state((1.0, 0.0, 0.0, 1.0), ctm)
    with pytest.raises(ValueError, match="illegal values"):
        stripper._origin_matrix(state, 5.0, 5.0).get_translate_x()  # noqa: SLF001
    with pytest.raises(ValueError, match="illegal values"):
        stripper._origin_translate(state, 5.0, 5.0)  # noqa: SLF001


# --------------------------------------------------------------------------
# _scale_and_dir: bit-identical to recomputing, translation-invariant, cached
# --------------------------------------------------------------------------


@pytest.mark.parametrize("tm", _TMS)
@pytest.mark.parametrize("ctm", _CTMS)
def test_scale_and_dir_matches_text_rendering_matrix(
    tm: tuple[float, float, float, float], ctm: Matrix
) -> None:
    stripper = PDFTextStripper()
    state = _make_state(tm, ctm)
    trm = stripper._text_rendering_matrix(state)  # noqa: SLF001
    want = (
        trm.get_scaling_factor_x(),
        trm.get_scaling_factor_y(),
        stripper._text_dir(trm),  # noqa: SLF001
    )
    got = stripper._scale_and_dir(state)  # noqa: SLF001
    assert tuple(_bits(v) for v in got) == tuple(_bits(v) for v in want)


def test_scale_and_dir_is_translation_invariant_and_cached() -> None:
    stripper = PDFTextStripper()
    state = _make_state((14.0, 0.0, 0.0, 14.0), _CTMS[1])
    first = stripper._scale_and_dir(state)  # noqa: SLF001
    assert state._trm_cache is first  # cached  # noqa: SLF001
    # Moving the cursor (as Tj/Td do) must NOT change the derived values.
    state.text_x += 500.0
    state.text_y -= 42.0
    trm = stripper._text_rendering_matrix(state)  # noqa: SLF001
    fresh = (
        trm.get_scaling_factor_x(),
        trm.get_scaling_factor_y(),
        stripper._text_dir(trm),  # noqa: SLF001
    )
    assert tuple(_bits(v) for v in fresh) == tuple(_bits(v) for v in first)
    # Cache still serves the same object (no invalidation on cursor move).
    assert stripper._scale_and_dir(state) is first  # noqa: SLF001


def _dispatch(stripper: PDFTextStripper, op: str, operands, state) -> None:
    stripper._dispatch(op, operands, state, [])  # noqa: SLF001


@pytest.mark.parametrize(
    ("op", "operands"),
    [
        ("BT", []),
        (
            "Tm",
            [COSInteger.get(2), COSFloat("0"), COSFloat("0"),
             COSInteger.get(2), COSFloat("5"), COSFloat("6")],
        ),
        ("Ts", [COSFloat("3")]),
        ("Q", None),  # filled below (needs a pushed state)
        (
            "cm",
            [COSFloat("2"), COSFloat("0"), COSFloat("0"),
             COSFloat("2"), COSFloat("0"), COSFloat("0")],
        ),
    ],
)
def test_invalidating_operators_drop_the_cache(op: str, operands) -> None:
    stripper = PDFTextStripper()
    state = _make_state((1.0, 0.0, 0.0, 1.0), Matrix())
    state.in_text_object = True
    if op == "Q":
        # Q restores a pushed CTM — arrange one to pop.
        _dispatch(stripper, "q", [], state)
        operands = []
    # Warm the cache.
    stripper._scale_and_dir(state)  # noqa: SLF001
    assert state._trm_cache is not None  # noqa: SLF001
    _dispatch(stripper, op, operands, state)
    assert state._trm_cache is None, op  # noqa: SLF001


def test_cursor_operator_td_does_not_drop_cache() -> None:
    stripper = PDFTextStripper()
    state = _make_state((1.0, 0.0, 0.0, 1.0), Matrix())
    state.in_text_object = True
    stripper._scale_and_dir(state)  # noqa: SLF001
    warmed = state._trm_cache  # noqa: SLF001
    _dispatch(stripper, "Td", [COSFloat("7"), COSFloat("9")], state)
    # Td only moves the cursor; the derived scale/dir cache stays valid.
    assert state._trm_cache is warmed  # noqa: SLF001
