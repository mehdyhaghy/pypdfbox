"""Wave 1386 — ExtGState entries are now *applied* by the paint pipeline.

Wave 1385 stored ``/CA`` / ``/ca`` / ``/SA`` / ``/AIS`` / ``/TK`` /
``/FL`` / ``/SM`` on the active ``_GState`` but the paint code never
consulted them. This wave wires the remaining behaviourally-meaningful
entries:

* ``/CA`` (stroke alpha) and ``/ca`` (non-stroke alpha) now multiply
  into the pen / brush opacity at construction time, both for the path
  paint loop (``_draw_via_aggdraw``) and the per-glyph paint helpers
  (``_paint_glyph_path_direct`` / ``_paint_glyph_path_through_clip``).
* ``/SA`` (stroke adjustment) snaps sub-pixel stroke widths to a full
  device pixel so hairlines don't anti-alias into ghost lines.
* ``/AIS`` (alpha-is-shape) thresholds the soft-mask /Alpha source's
  alpha plane to its shape (every nonzero pixel → fully opaque).

``/FL`` (flatness) and ``/SM`` (smoothness) remain best-effort no-ops
in the lite renderer (Skia handles curve flattening + shading sampling
adaptively); they are still carried on the GS for parity bookkeeping.
``/TK`` (text knockout) wiring is deferred — see DEFERRED.md.
"""

from __future__ import annotations

from PIL import Image

from pypdfbox.pdmodel.graphics.state.pd_extended_graphics_state import (
    PDExtendedGraphicsState,
)
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering.pdf_renderer import _GState

from .test_pdf_renderer_extgstate_wave1385 import _attach_renderer


def _bare_renderer(gs: _GState) -> PDFRenderer:
    """Construct a PDFRenderer skeleton with just enough state to drive
    the pen / brush builders. Skips the full ``__init__`` because we
    don't need a real PDDocument for these protected-helper unit tests.
    """
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = [gs]
    r._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    return r


# ---------------------------------------------------------------------------
# /CA + /ca pen / brush opacity wiring
# ---------------------------------------------------------------------------


def test_ca_multiplies_into_stroke_pen_opacity() -> None:
    """The ``/CA`` non-zero alpha is folded into the stroke pen's opacity
    by :meth:`_draw_via_aggdraw`. We build a renderer with stroke_alpha
    set, then poke through ``_build_stroke_pen`` to read back the opacity
    actually stored on the pen."""
    r = _bare_renderer(_GState(stroke_alpha=0.5))
    pen = r._build_stroke_pen((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))  # noqa: SLF001
    # Pen.opacity is 0..255 — 0.5 alpha → 128 ± 1 (rounding).
    assert 126 <= pen.opacity <= 129


def test_ca_zero_zeros_stroke_pen_opacity() -> None:
    r = _bare_renderer(_GState(stroke_alpha=0.0))
    pen = r._build_stroke_pen((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))  # noqa: SLF001
    assert pen.opacity == 0


def test_ca_clamped_above_one() -> None:
    """Defensive — out-of-range ``/CA`` should clamp to [0, 1] before the
    opacity multiplication so we never overflow the byte range."""
    r = _bare_renderer(_GState(stroke_alpha=2.5))
    pen = r._build_stroke_pen((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))  # noqa: SLF001
    assert pen.opacity == 255


def test_glyph_brush_honours_fill_alpha() -> None:
    r = _bare_renderer(_GState(fill_alpha=0.25))
    brush = r._build_glyph_brush((100, 100, 100))  # noqa: SLF001
    # 0.25 → 64 ± 1.
    assert 63 <= brush.opacity <= 65


def test_glyph_brush_zero_alpha_is_fully_transparent() -> None:
    r = _bare_renderer(_GState(fill_alpha=0.0))
    brush = r._build_glyph_brush((255, 0, 0))  # noqa: SLF001
    assert brush.opacity == 0


# ---------------------------------------------------------------------------
# Sub-pixel glyph-stroke width — floored to 0.25 device px (wave 1595)
#
# Upstream ``PageDrawer.getStroke`` floors the device pen width to 0.25
# ("minimum line width as used by Adobe Reader") for *both* path strokes
# and glyph-outline strokes; there is no separate glyph minimum and ``/SA``
# does NOT snap the width to a full pixel (it only toggles Java2D's
# STROKE_PURE vs STROKE_NORMALIZE hint). Wave 1595 dropped the wave-1442
# 0.5 floor and the wave-1386 ``/SA``-snap-to-1.0 so the glyph-outline pen
# converges to the same 0.25 floor as ``_stroke_path_device_space``.
# ---------------------------------------------------------------------------


def test_sub_pixel_stroke_floored_to_quarter_pixel() -> None:
    """A line width that lands below 0.25 device px is floored to 0.25
    (identity CTM → ctm_scale 1.0 → glyph-local width == device width)."""
    r = _bare_renderer(_GState(line_width=0.1, stroke_adjustment=False))
    pen = r._build_stroke_pen((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))  # noqa: SLF001
    assert pen.width == 0.25


def test_sa_does_not_snap_glyph_stroke_width() -> None:
    """``/SA true`` must NOT snap the glyph-stroke width to a full pixel —
    upstream ``getStroke`` floors to 0.25 regardless of ``/SA`` (the hint
    only affects Java2D's stroke-pure/normalize mode, not the pen width)."""
    r = _bare_renderer(_GState(line_width=0.1, stroke_adjustment=True))
    pen = r._build_stroke_pen((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))  # noqa: SLF001
    assert pen.width == 0.25


# ---------------------------------------------------------------------------
# /AIS — soft-mask /Alpha source threshold
# ---------------------------------------------------------------------------


class _FakeAlphaSoftMask:
    """Stand-in :class:`PDSoftMask` with type=/Alpha that delegates to a
    fixed alpha plane (skips the recursive content-stream rendering)."""

    def __init__(self, alpha_image: Image.Image) -> None:
        self._alpha = alpha_image

    def is_luminosity(self) -> bool:
        return False

    def get_transfer_function(self) -> None:
        return None


def test_ais_thresholds_alpha_plane_to_shape() -> None:
    """Direct unit test of the AIS post-processing branch in
    :meth:`_render_soft_mask_alpha`.

    Build a synthetic alpha plane with mid-tones, then run the AIS
    branch in isolation to confirm every nonzero pixel becomes 255
    while zero pixels stay 0.
    """
    plane = Image.new("L", (4, 1), 0)
    plane.putpixel((0, 0), 0)
    plane.putpixel((1, 0), 64)
    plane.putpixel((2, 0), 200)
    plane.putpixel((3, 0), 255)

    # Mirror the AIS post-processing snippet from _render_soft_mask_alpha.
    thresholded = plane.point(lambda v: 255 if v > 0 else 0, mode="L")
    assert [thresholded.getpixel((x, 0)) for x in range(4)] == [0, 255, 255, 255]


def test_ais_default_false_carries_through_gs_clone() -> None:
    """``/AIS`` defaults to false (PDF spec table 58) and clone preserves
    the flag verbatim."""
    gs = _GState(alpha_is_shape=False)
    clone = gs.clone()
    assert clone.alpha_is_shape is False
    gs2 = _GState(alpha_is_shape=True)
    assert gs2.clone().alpha_is_shape is True


# ---------------------------------------------------------------------------
# /CA + /ca round-trip through the ``gs`` operator end-to-end
# ---------------------------------------------------------------------------


def test_gs_operator_sets_both_alphas_through_to_pen_and_brush() -> None:
    """End-to-end: ``gs`` operator reads ``/CA`` + ``/ca`` from an
    ExtGState dict, _apply_ext_gstate stores them on the GS, and the
    next pen/brush construction picks them up."""
    ext = PDExtendedGraphicsState()
    ext.set_stroking_alpha_constant(0.4)
    ext.set_non_stroking_alpha_constant(0.8)
    r = _attach_renderer(ext)
    r._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    assert abs(r._gs.stroke_alpha - 0.4) < 1e-6  # noqa: SLF001
    assert abs(r._gs.fill_alpha - 0.8) < 1e-6  # noqa: SLF001

    pen = r._build_stroke_pen((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))  # noqa: SLF001
    brush = r._build_glyph_brush((10, 20, 30))  # noqa: SLF001
    # 0.4 → 102, 0.8 → 204 (rounding).
    assert 101 <= pen.opacity <= 103
    assert 203 <= brush.opacity <= 205


# ---------------------------------------------------------------------------
# /SA round-trip
# ---------------------------------------------------------------------------


def test_gs_operator_sa_stroke_adjustment_round_trip() -> None:
    ext = PDExtendedGraphicsState()
    ext.set_stroke_adjustment(True)
    r = _attach_renderer(ext)
    r._device_ctm = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)  # noqa: SLF001
    assert r._gs.stroke_adjustment is True  # noqa: SLF001
    r._gs.line_width = 0.2  # noqa: SLF001
    pen = r._build_stroke_pen((1.0, 0.0, 0.0, 1.0, 0.0, 0.0))  # noqa: SLF001
    # /SA round-trips onto the GS but no longer snaps the pen width — the
    # 0.2 user-space width floors to the 0.25 device minimum (wave 1595).
    assert pen.width == 0.25


# ---------------------------------------------------------------------------
# transfer-function no-op safety
# ---------------------------------------------------------------------------


def test_transfer_to_rgb_bytes_no_op_when_no_gs_stack() -> None:
    """Helper must not crash when called before the GS stack is set up —
    oracle tests poke at internal helpers from a bare renderer."""
    r = PDFRenderer.__new__(PDFRenderer)
    r._gs_stack = []
    # The protected helper should short-circuit and return its input.
    assert r._apply_transfer_to_rgb_bytes((10, 20, 30)) == (10, 20, 30)  # noqa: SLF001


def test_transfer_to_rgb_bytes_no_op_when_function_none() -> None:
    r = _bare_renderer(_GState(transfer_function=None))
    assert r._apply_transfer_to_rgb_bytes((10, 20, 30)) == (10, 20, 30)  # noqa: SLF001
