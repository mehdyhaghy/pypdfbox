"""Wave 1591 — TextPosition construction fuzz (text engine ``showGlyph`` path).

Hammers the per-glyph / per-run ``TextPosition`` the lite stripper builds in
:meth:`pypdfbox.text.PDFTextStripper._emit` and friends, the conceptual
analogue of Apache PDFBox's ``LegacyPDFStreamEngine.showGlyph`` →
``processTextPosition``. Each case drives a tiny synthetic content stream
through the *real* engine (``PDFTextStripper.get_text`` with a
``process_text_position`` collector) and pins the constructed position's
geometry against the value upstream's ``TextPosition`` would carry:

* glyph origin (``x`` / ``y``) recovered from ``textMatrix × CTM`` (the
  text-rendering matrix), including the point size folded into ``Tm``;
* displayed run width = ``glyphDisplacement × fontSize × Tz`` transformed by
  the matrix X scaling factor;
* effective font size (the matrix Y scaling × ``Tf``) carried on
  :attr:`font_size`, and the X-scaled ``getFontSizeInPt()`` (upstream's
  ``fontSize × textMatrix.getScalingFactorX()``);
* the space / word width that drives word-break detection, scaled by ``Tz``
  and the matrix X scale;
* the decoded unicode string for the glyph(s);
* the direction adjustment (``getDir`` / ``getXDirAdj`` / ``getYDirAdj``) for
  cardinal-rotated text matrices (0 / 90 / 180 / 270);
* the per-character ``individual_widths`` array;
* the text rise (``Ts``) baseline offset folded into the origin.

The harness is self-contained (no live Java oracle): expectations are
derived analytically from the PDF text-state algebra so the suite runs
everywhere. ``/F0`` is an unresolved font resource, so per-glyph advances
fall back to the lite stripper's deterministic 0.5-em monospace estimate —
which is exactly what keeps these origin / width assertions analytic.

Hand-written (not ported from upstream JUnit).
"""

from __future__ import annotations

import math

import pytest

from pypdfbox.cos import COSStream
from pypdfbox.pdmodel import PDDocument, PDPage, PDRectangle
from pypdfbox.text import PDFTextStripper, TextPosition

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------

_PAGE_W = 612.0
_PAGE_H = 792.0
_EPS = 1e-4


def _capture(content: bytes, *, rotation: int = 0) -> list[TextPosition]:
    """Drive ``content`` through the real engine and return every emitted
    :class:`TextPosition` in construction order."""
    doc = PDDocument()
    page = PDPage(PDRectangle(0.0, 0.0, _PAGE_W, _PAGE_H))
    page.set_rotation(rotation)
    stream = COSStream()
    stream.set_data(content)
    page.set_contents(stream)
    doc.add_page(page)

    captured: list[TextPosition] = []

    class _Collector(PDFTextStripper):
        def process_text_position(self, text: TextPosition) -> None:  # type: ignore[override]
            captured.append(text)

    _Collector().get_text(doc)
    doc.close()
    return captured


# Per-character advance the lite stripper assigns to an unresolved font:
# half the font size in text space.
def _per_char(font_size: float) -> float:
    return font_size * 0.5


# ---------------------------------------------------------------------------
# Origin: textMatrix × CTM translation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("tx", "ty"),
    [(100.0, 700.0), (0.0, 0.0), (50.5, 12.25), (611.0, 1.0), (10.0, 791.0)],
)
def test_origin_matches_td_translation(tx: float, ty: float) -> None:
    content = b"BT /F0 12 Tf %s %s Td (A) Tj ET" % (
        repr(tx).encode(),
        repr(ty).encode(),
    )
    runs = _capture(content)
    assert len(runs) == 1
    assert runs[0].x == pytest.approx(tx, abs=_EPS)
    assert runs[0].y == pytest.approx(ty, abs=_EPS)


def test_origin_with_point_size_folded_into_tm() -> None:
    """``24 0 0 24 100 700 Tm`` with ``1 Tf`` puts the origin at (100, 700)
    — the matrix scale is folded into the rendered glyph, not the origin."""
    runs = _capture(b"BT /F0 1 Tf 24 0 0 24 100 700 Tm (AB) Tj ET")
    assert len(runs) == 1
    assert runs[0].x == pytest.approx(100.0, abs=_EPS)
    assert runs[0].y == pytest.approx(700.0, abs=_EPS)


def test_origin_with_cm_translation_composed() -> None:
    """A page ``cm`` translation composes into the device origin
    (textMatrix × CTM)."""
    runs = _capture(b"q 1 0 0 1 30 40 cm BT /F0 12 Tf 100 700 Td (X) Tj ET Q")
    assert len(runs) == 1
    assert runs[0].x == pytest.approx(130.0, abs=_EPS)
    assert runs[0].y == pytest.approx(740.0, abs=_EPS)


# ---------------------------------------------------------------------------
# Displayed width: glyphDisplacement × fontSize × Tz, X-scaled by the matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("font_size", [6.0, 12.0, 18.0, 24.0, 48.0])
def test_run_width_is_glyph_advance_times_font_size(font_size: float) -> None:
    text = "ABC"
    content = b"BT /F0 %s Tf 100 700 Td (%s) Tj ET" % (
        repr(font_size).encode(),
        text.encode(),
    )
    runs = _capture(content)
    assert len(runs) == 1
    expected = len(text) * _per_char(font_size)
    assert runs[0].width == pytest.approx(expected, abs=1e-3)


@pytest.mark.parametrize(
    ("tz_percent", "factor"),
    [(50, 0.5), (100, 1.0), (150, 1.5), (200, 2.0)],
)
def test_run_width_scaled_by_horizontal_scaling_tz(
    tz_percent: int, factor: float
) -> None:
    """``Tz`` (horizontal text scaling, percent) condenses / expands the
    displayed width — the word-gap heuristic measures the scaled value."""
    content = b"BT /F0 12 Tf %d Tz 100 700 Td (AB) Tj ET" % tz_percent
    runs = _capture(content)
    assert len(runs) == 1
    expected = 2 * _per_char(12.0) * factor
    assert runs[0].width == pytest.approx(expected, abs=1e-3)


def test_run_width_scaled_by_matrix_x_scale() -> None:
    """A 3× horizontal ``Tm`` scale multiplies the device-space run width
    by the matrix X scaling factor."""
    runs = _capture(b"BT /F0 12 Tf 3 0 0 1 100 700 Tm (AB) Tj ET")
    assert len(runs) == 1
    expected = 2 * _per_char(12.0) * 3.0
    assert runs[0].width == pytest.approx(expected, abs=1e-3)


# ---------------------------------------------------------------------------
# Font size: effective (Y-scaled) vs getFontSizeInPt (X-scaled)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("font_size", [8.0, 11.0, 14.0, 36.0])
def test_unscaled_font_size_round_trips(font_size: float) -> None:
    content = b"BT /F0 %s Tf 100 700 Td (X) Tj ET" % repr(font_size).encode()
    runs = _capture(content)
    assert runs[0].font_size == pytest.approx(font_size, abs=_EPS)
    assert runs[0].get_font_size_in_pt() == pytest.approx(font_size, abs=_EPS)


def test_font_size_uses_matrix_y_scale() -> None:
    """``font_size`` carries the effective (Y-scaled) glyph size — matrix Y
    scale × ``Tf``."""
    runs = _capture(b"BT /F0 2 Tf 1 0 0 5 100 700 Tm (X) Tj ET")
    assert runs[0].font_size == pytest.approx(10.0, abs=_EPS)


def test_font_size_in_pt_uses_matrix_x_scale() -> None:
    """``getFontSizeInPt()`` mirrors upstream ``fontSize × getScalingFactorX()``
    — the X scaling factor, independent of a non-uniform Y scale. This is
    the wave-1591 fix: previously the X-scaled point size was never threaded
    so it fell back to the Y-scaled ``font_size`` and diverged on a
    non-uniform text matrix."""
    # a = 24 (X scale), d = 12 (Y scale), Tf = 1.
    runs = _capture(b"BT /F0 1 Tf 24 0 0 12 100 700 Tm (AB) Tj ET")
    assert runs[0].get_font_size_in_pt() == pytest.approx(24.0, abs=_EPS)
    # The effective (Y-scaled) font size is still the 12.
    assert runs[0].font_size == pytest.approx(12.0, abs=_EPS)


def test_font_size_in_pt_equals_font_size_for_uniform_matrix() -> None:
    """Uniform scale: X scale == Y scale, so the point size and the
    effective font size coincide (the pre-fix invariant the oracle
    fixtures pin)."""
    runs = _capture(b"BT /F0 1 Tf 24 0 0 24 100 700 Tm (AB) Tj ET")
    assert runs[0].font_size == pytest.approx(24.0, abs=_EPS)
    assert runs[0].get_font_size_in_pt() == pytest.approx(24.0, abs=_EPS)


# ---------------------------------------------------------------------------
# Space / word width (word-break source)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("font_size", [6.0, 12.0, 24.0])
def test_width_of_space_scales_with_font_size(font_size: float) -> None:
    content = b"BT /F0 %s Tf 100 700 Td (AB) Tj ET" % repr(font_size).encode()
    runs = _capture(content)
    # Unresolved font: width_of_space falls back to the per-char advance.
    assert runs[0].width_of_space == pytest.approx(_per_char(font_size), abs=1e-3)


@pytest.mark.parametrize(
    ("tz_percent", "factor"), [(50, 0.5), (200, 2.0)]
)
def test_width_of_space_scaled_by_tz(tz_percent: int, factor: float) -> None:
    content = b"BT /F0 12 Tf %d Tz 100 700 Td (AB) Tj ET" % tz_percent
    runs = _capture(content)
    assert runs[0].width_of_space == pytest.approx(
        _per_char(12.0) * factor, abs=1e-3
    )


def test_width_of_space_scaled_by_matrix_x_scale() -> None:
    runs = _capture(b"BT /F0 12 Tf 2 0 0 1 100 700 Tm (AB) Tj ET")
    assert runs[0].width_of_space == pytest.approx(_per_char(12.0) * 2.0, abs=1e-3)


# ---------------------------------------------------------------------------
# Unicode mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["Hello", "A", " wide gap ", "MixedCASE123", "()parens"]
)
def test_unicode_preserved_for_ascii_runs(text: str) -> None:
    # Escape PDF string delimiters.
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = b"BT /F0 12 Tf 100 700 Td (%s) Tj ET" % escaped.encode("latin-1")
    runs = _capture(content)
    assert "".join(r.text for r in runs) == text
    for r in runs:
        assert r.get_unicode() == r.text
        assert r.get_character() == r.text


def test_unicode_high_byte_latin1_fallback() -> None:
    """A byte with no /ToUnicode resolves through the Latin-1 fallback."""
    runs = _capture(b"BT /F0 12 Tf 100 700 Td (caf\xe9) Tj ET")
    assert "".join(r.text for r in runs) == "café"


# ---------------------------------------------------------------------------
# Direction (getDir / getXDirAdj / getYDirAdj) for cardinal rotations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("matrix", "expected_dir"),
    [
        (b"1 0 0 1", 0.0),
        (b"0 1 -1 0", 90.0),
        (b"-1 0 0 -1", 180.0),
        (b"0 -1 1 0", 270.0),
    ],
)
def test_dir_for_cardinal_text_matrix(matrix: bytes, expected_dir: float) -> None:
    content = b"BT /F0 12 Tf %s 100 700 Tm (X) Tj ET" % matrix
    runs = _capture(content)
    assert runs[0].get_dir() == expected_dir


def test_x_dir_adj_unrotated_is_x() -> None:
    runs = _capture(b"BT /F0 12 Tf 100 700 Td (X) Tj ET")
    tp = runs[0]
    tp.page_width = _PAGE_W
    tp.page_height = _PAGE_H
    assert tp.get_x_dir_adj() == pytest.approx(tp.x, abs=_EPS)
    assert tp.get_y_dir_adj() == pytest.approx(tp.y, abs=_EPS)


def test_x_dir_adj_90_swaps_axes() -> None:
    """For a 90-degree run, ``getXDirAdj`` reports the (rotated) Y axis,
    ``getYDirAdj`` reports ``page_width - x`` — the rotated reading frame."""
    runs = _capture(b"BT /F0 12 Tf 0 1 -1 0 100 700 Tm (X) Tj ET")
    tp = runs[0]
    tp.page_width = _PAGE_W
    tp.page_height = _PAGE_H
    assert tp.get_dir() == 90.0
    assert tp.get_x_dir_adj() == pytest.approx(tp.y, abs=_EPS)
    assert tp.get_y_dir_adj() == pytest.approx(_PAGE_W - tp.x, abs=_EPS)
    # The upstream-named alias dispatches identically.
    assert tp.get_x_directional_adj() == tp.get_x_dir_adj()
    assert tp.get_y_directional_adj() == tp.get_y_dir_adj()


def test_x_dir_adj_180_and_270() -> None:
    tp180 = _capture(b"BT /F0 12 Tf -1 0 0 -1 100 700 Tm (X) Tj ET")[0]
    tp180.page_width = _PAGE_W
    tp180.page_height = _PAGE_H
    assert tp180.get_dir() == 180.0
    assert tp180.get_x_dir_adj() == pytest.approx(_PAGE_W - tp180.x, abs=_EPS)
    assert tp180.get_y_dir_adj() == pytest.approx(_PAGE_H - tp180.y, abs=_EPS)

    tp270 = _capture(b"BT /F0 12 Tf 0 -1 1 0 100 700 Tm (X) Tj ET")[0]
    tp270.page_width = _PAGE_W
    tp270.page_height = _PAGE_H
    assert tp270.get_dir() == 270.0
    assert tp270.get_x_dir_adj() == pytest.approx(_PAGE_H - tp270.y, abs=_EPS)
    assert tp270.get_y_dir_adj() == pytest.approx(tp270.x, abs=_EPS)


# ---------------------------------------------------------------------------
# Individual character widths array
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("text", ["A", "AB", "ABCDE"])
def test_individual_widths_sum_to_run_width(text: str) -> None:
    content = b"BT /F0 12 Tf 100 700 Td (%s) Tj ET" % text.encode()
    runs = _capture(content)
    assert len(runs) == 1
    widths = runs[0].get_individual_widths()
    assert len(widths) == len(text)
    assert sum(widths) == pytest.approx(runs[0].width, abs=1e-3)


def test_individual_widths_fallback_distribution() -> None:
    """A synthetic position with only a run-level width distributes evenly."""
    tp = TextPosition(text="abcd", x=0.0, y=0.0, font_size=10.0, width=40.0)
    assert tp.get_individual_widths() == [10.0, 10.0, 10.0, 10.0]


# ---------------------------------------------------------------------------
# Text rise (Ts) baseline offset
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("rise", [0.0, 3.0, 5.5, -4.0])
def test_text_rise_shifts_origin_y(rise: float) -> None:
    """``Ts`` lifts / lowers the glyph origin along the (unrotated) text
    matrix Y axis — folded into the device origin as
    ``[1 0 0 1 0 rise] × Tm × ctm``."""
    content = b"BT /F0 12 Tf 100 700 Td %s Ts (R) Tj ET" % repr(rise).encode()
    runs = _capture(content)
    assert len(runs) == 1
    assert runs[0].y == pytest.approx(700.0 + rise, abs=_EPS)
    # Rise does not move X for an unrotated matrix.
    assert runs[0].x == pytest.approx(100.0, abs=_EPS)


def test_text_rise_rotates_with_90_matrix() -> None:
    """Under a 90-degree ``Tm`` the rise shifts along the rotated local Y
    axis, so it moves the device X (origin = ``parameterMatrix × Tm``)."""
    runs = _capture(b"BT /F0 12 Tf 0 1 -1 0 100 700 Tm 5 Ts (R) Tj ET")
    assert len(runs) == 1
    # [1 0 0 1 0 5] × [0 1 -1 0 100 700] => translate (100 - 5, 700)
    assert runs[0].x == pytest.approx(95.0, abs=_EPS)
    assert runs[0].y == pytest.approx(700.0, abs=_EPS)


# ---------------------------------------------------------------------------
# Text-matrix snapshot fidelity
# ---------------------------------------------------------------------------


def test_text_matrix_snapshot_carries_scale_and_translate() -> None:
    runs = _capture(b"BT /F0 1 Tf 24 0 0 18 100 700 Tm (X) Tj ET")
    tm = runs[0].get_text_matrix()
    assert tm is not None
    assert tm[0] == pytest.approx(24.0, abs=_EPS)
    assert tm[3] == pytest.approx(18.0, abs=_EPS)
    assert tm[4] == pytest.approx(100.0, abs=_EPS)
    assert tm[5] == pytest.approx(700.0, abs=_EPS)


def test_x_scale_y_scale_derived_from_matrix() -> None:
    runs = _capture(b"BT /F0 1 Tf 24 0 0 18 100 700 Tm (X) Tj ET")
    tp = runs[0]
    assert tp.get_x_scale() == pytest.approx(24.0, abs=_EPS)
    assert tp.get_y_scale() == pytest.approx(18.0, abs=_EPS)


def test_x_scale_for_rotated_matrix_is_magnitude() -> None:
    """A 90-degree matrix has ``a == 0`` but a unit X-basis magnitude — the
    scale is the hypot, not the raw slot."""
    runs = _capture(b"BT /F0 12 Tf 0 1 -1 0 100 700 Tm (X) Tj ET")
    assert runs[0].get_x_scale() == pytest.approx(1.0, abs=_EPS)
    assert runs[0].get_y_scale() == pytest.approx(1.0, abs=_EPS)


# ---------------------------------------------------------------------------
# TJ array: numeric adjustments + per-string runs
# ---------------------------------------------------------------------------


def test_tj_array_emits_string_runs() -> None:
    runs = _capture(b"BT /F0 12 Tf 100 700 Td [(AB) -250 (CD)] TJ ET")
    assert "".join(r.text for r in runs) == "ABCD"
    for r in runs:
        assert r.font_size == pytest.approx(12.0, abs=_EPS)
        assert r.get_font_size_in_pt() == pytest.approx(12.0, abs=_EPS)


def test_tj_negative_adjustment_advances_cursor() -> None:
    """A negative ``TJ`` number moves the cursor forward, so the second
    run starts to the right of the first run's right edge."""
    runs = _capture(b"BT /F0 12 Tf 100 700 Td [(AB) -2000 (CD)] TJ ET")
    assert len(runs) == 2
    first, second = runs
    # -2000/1000 em × 12pt = +24pt extra gap on top of the run advance.
    assert second.x > first.x + first.width


# ---------------------------------------------------------------------------
# Direction snap edge cases (non-cardinal angles snap to nearest quadrant)
# ---------------------------------------------------------------------------


def test_dir_snaps_small_rotation_to_zero() -> None:
    """A tiny rotation (~5 degrees) snaps to the 0-degree quadrant."""
    rad = math.radians(5.0)
    a = math.cos(rad)
    b = math.sin(rad)
    content = b"BT /F0 12 Tf %s %s %s %s 100 700 Tm (X) Tj ET" % (
        repr(a).encode(),
        repr(b).encode(),
        repr(-b).encode(),
        repr(a).encode(),
    )
    runs = _capture(content)
    assert runs[0].get_dir() == 0.0
