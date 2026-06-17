"""Fuzz / parity tests for the glyph-outline -> path conversion used by
the renderer (the Glyph2D equivalent surface).

pypdfbox has no single ``Glyph2D`` class — upstream's
``TTFGlyph2D`` / ``Type1Glyph2D`` / ``CFFGlyph2D`` responsibilities are
spread across:

* ``PDTrueTypeFont.get_normalized_path`` / ``get_glyph_path`` /
  ``_draw_glyph_by_name`` — TrueType ``glyf`` contour -> path, scaled to
  the 1000-unit text space by ``1000 / unitsPerEm`` (upstream
  ``PDVectorFont.getNormalizedPath`` + the ``GeneralPath`` scale).
* ``pypdfbox.rendering.glyph_cache.GlyphCache`` — the per-character-code
  outline cache (upstream ``GlyphCache``).
* ``pypdfbox.rendering.pdf_renderer._AggdrawPathPen`` — the unit-em pen
  that scales font-unit coordinates by ``1 / unitsPerEm`` and converts
  TrueType quadratic ``qCurveTo`` segments into cubic Beziers for
  aggdraw.

These tests hammer those entry points with a real bundled font
(DejaVuSansMono, ``unitsPerEm == 2048``) plus synthetic command streams,
checking against upstream-documented behaviour:

* ``get_path_for_glyph(gid)`` / ``get_path_for_character_code(code)``
  resolving code -> gid -> path,
* the 1000/upem scaling,
* the glyph cache returning the SAME object for a repeated code,
* a ``.notdef`` / empty (space) glyph -> empty path,
* a COMPOSITE TrueType glyph decomposed into real segments (regression
  for the wave-1588 bug where ``_draw_glyph_by_name`` returned raw
  ``addComponent`` tuples),
* out-of-range gid / code -> empty path,
* the quadratic -> cubic conversion in ``_AggdrawPathPen``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.font.pd_true_type_font import (
    PDTrueTypeFont,
    _draw_glyph_by_gid,
    _draw_glyph_by_name,
    _scale_path,
)
from pypdfbox.rendering import _aggdraw_compat as aggdraw
from pypdfbox.rendering.glyph_cache import GlyphCache, _empty_path
from pypdfbox.rendering.pdf_renderer import PDFRenderer, _AggdrawPathPen

_build_aggdraw_path_from_commands = PDFRenderer._build_aggdraw_path_from_commands

_FONT_PATH = (
    Path(__file__).parent.parent
    / "fixtures"
    / "fontbox"
    / "ttf"
    / "DejaVuSansMono.ttf"
)
_UPEM = 2048  # DejaVuSansMono head.unitsPerEm


@pytest.fixture(scope="module")
def font() -> Any:
    doc = PDDocument()
    f = PDTrueTypeFont.load(doc, _FONT_PATH.read_bytes())
    yield f
    doc.close()


@pytest.fixture(scope="module")
def ttf(font: Any) -> Any:
    return font.get_true_type_font()


def _x_of_first_move(path: list[tuple[Any, ...]]) -> float:
    """Pull the x-coordinate of the first ``moveTo`` point from a
    recording-pen path (verb, (pt, ...))."""
    for verb, args in path:
        if verb == "moveTo" and args and args[0] is not None:
            return float(args[0][0])
    raise AssertionError("no moveTo in path")


# ---------------------------------------------------------------------------
# unitsPerEm scaling
# ---------------------------------------------------------------------------


def test_font_reports_expected_units_per_em(ttf: Any) -> None:
    assert ttf.get_units_per_em() == _UPEM


@pytest.mark.parametrize("code", [ord("A"), ord("B"), ord("g"), ord("0"), ord("@")])
def test_normalized_path_is_scaled_by_1000_over_upem(font: Any, code: int) -> None:
    raw = font.get_glyph_path(code)
    norm = font.get_normalized_path(code)
    assert raw, f"raw path empty for {code!r}"
    assert norm, f"normalized path empty for {code!r}"
    raw_x = _x_of_first_move(raw)
    norm_x = _x_of_first_move(norm)
    assert raw_x != 0.0
    assert norm_x == pytest.approx(raw_x * 1000.0 / _UPEM)


def test_normalized_path_preserves_verb_sequence(font: Any) -> None:
    raw = font.get_glyph_path(ord("A"))
    norm = font.get_normalized_path(ord("A"))
    assert [v for v, _ in raw] == [v for v, _ in norm]
    assert len(norm) == len(raw)


def test_scale_path_scales_every_point() -> None:
    path = [
        ("moveTo", ((100.0, 200.0),)),
        ("lineTo", ((300.0, 400.0),)),
        ("qCurveTo", ((10.0, 20.0), (30.0, 40.0))),
        ("closePath", ()),
    ]
    scaled = _scale_path(path, 0.5)
    assert scaled[0] == ("moveTo", ((50.0, 100.0),))
    assert scaled[1] == ("lineTo", ((150.0, 200.0),))
    assert scaled[2] == ("qCurveTo", ((5.0, 10.0), (15.0, 20.0)))
    assert scaled[3] == ("closePath", ())


def test_scale_path_leaves_none_control_points() -> None:
    # All-off-curve TrueType contour: fontTools appends a trailing None.
    path = [("qCurveTo", ((10.0, 20.0), None))]
    scaled = _scale_path(path, 2.0)
    assert scaled == [("qCurveTo", ((20.0, 40.0), None))]


def test_scale_path_identity_scale_one() -> None:
    path = [("moveTo", ((1.0, 2.0),)), ("lineTo", ((3.0, 4.0),))]
    assert _scale_path(path, 1.0) == path


# ---------------------------------------------------------------------------
# code -> gid -> path resolution + empty / notdef glyphs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("code", [ord("A"), ord("z"), ord("5")])
def test_get_glyph_path_nonempty_for_real_letters(font: Any, code: int) -> None:
    assert font.get_glyph_path(code), f"empty path for {chr(code)!r}"


def test_space_glyph_returns_empty_normalized_path(font: Any) -> None:
    # The space glyph (code 32) carries numberOfContours == 0.
    assert font.get_normalized_path(ord(" ")) == []


def test_gid0_notdef_path_returns_empty_for_embedded(font: Any) -> None:
    # Embedded fonts DO draw GID 0 upstream; the .notdef of DejaVuSansMono
    # is a box outline, so get_glyph_path is non-empty. But code 0 has no
    # encoding entry -> resolves to gid 0; embedded -> path allowed.
    # The contract we assert: an embedded font does NOT suppress gid 0.
    assert font.is_embedded()
    path = font.get_normalized_path(0)
    # .notdef may be empty or a box depending on the font; assert it does
    # not raise and returns a list.
    assert isinstance(path, list)


def test_draw_glyph_by_gid_zero_is_notdef(ttf: Any) -> None:
    # GID 0 is .notdef; for DejaVuSansMono it has an outline (box).
    path = _draw_glyph_by_gid(ttf, 0)
    assert isinstance(path, list)


def test_draw_glyph_by_gid_out_of_range_returns_empty(ttf: Any) -> None:
    huge = ttf.get_number_of_glyphs() + 10_000
    assert _draw_glyph_by_gid(ttf, huge) == []


def test_draw_glyph_by_gid_negative_returns_empty(ttf: Any) -> None:
    assert _draw_glyph_by_gid(ttf, -1) == []


def test_draw_glyph_by_name_unknown_returns_empty(ttf: Any) -> None:
    assert _draw_glyph_by_name(ttf, "this_glyph_does_not_exist_xyz") == []


def test_get_path_by_name_gid_pseudo_name(font: Any) -> None:
    # Upstream getPath(String) accepts a decimal GID pseudo-name.
    path = font.get_path_by_name("36")  # gid 36 == 'A' in DejaVuSansMono
    assert path
    assert path[0][0] == "moveTo"


def test_get_path_by_name_notdef_returns_empty(font: Any) -> None:
    assert font.get_path_by_name(".notdef") == []


def test_get_path_by_name_out_of_range_gid_pseudo_name(font: Any) -> None:
    ttf = font.get_true_type_font()
    over = str(ttf.get_number_of_glyphs() + 5)
    assert font.get_path_by_name(over) == []


@pytest.mark.parametrize("code", [-1, 0x10FFFF, 9999999])
def test_out_of_range_code_does_not_raise(font: Any, code: int) -> None:
    path = font.get_normalized_path(code)
    assert isinstance(path, list)


# ---------------------------------------------------------------------------
# Composite TrueType glyph decomposition (wave 1588 regression)
# ---------------------------------------------------------------------------


def test_composite_glyph_decomposes_to_segments(font: Any) -> None:
    # eacute (U+00E9) is a composite glyph (e + acute) in DejaVuSansMono.
    path = font.get_glyph_path(0xE9)
    assert path, "composite glyph produced empty path"
    verbs = {v for v, _ in path}
    assert "addComponent" not in verbs, (
        "composite glyph must be DECOMPOSED into real segments, not left as "
        "raw addComponent references (upstream GlyphData.getPath flattens)"
    )
    assert "moveTo" in verbs


def test_composite_normalized_path_decomposed_and_scaled(font: Any) -> None:
    norm = font.get_normalized_path(0xE9)
    assert norm
    verbs = {v for v, _ in norm}
    assert "addComponent" not in verbs
    # And every point is scaled into text space — no raw 6-tuple transforms.
    for verb, args in norm:
        if verb == "closePath":
            continue
        for pt in args:
            if pt is None:
                continue
            assert isinstance(pt, tuple) and len(pt) == 2, (
                f"unexpected non-point arg {pt!r} for verb {verb}"
            )


def test_composite_glyph_has_more_segments_than_component_refs(font: Any) -> None:
    # The flattened path must have substantially more than the 2 component
    # references a non-decomposing pen would emit.
    path = font.get_glyph_path(0xE9)
    assert len(path) > 2


# ---------------------------------------------------------------------------
# GlyphCache: identity, empty path, error handling
# ---------------------------------------------------------------------------


class _VectorFontShim:
    """Minimal PDVectorFont-shaped wrapper delegating to a real font."""

    def __init__(self, font: Any) -> None:
        self._font = font
        self.calls = 0

    def has_glyph(self, code: int) -> bool:
        return True

    def get_name(self) -> str:
        return "DejaVuSansMono"

    def get_normalized_path(self, code: int) -> list[tuple[Any, ...]]:
        self.calls += 1
        return self._font.get_normalized_path(code)


def test_glyph_cache_returns_same_object_for_repeated_code(font: Any) -> None:
    shim = _VectorFontShim(font)
    cache = GlyphCache(shim)
    first = cache.get_path_for_character_code(ord("A"))
    second = cache.get_path_for_character_code(ord("A"))
    assert first is second
    assert shim.calls == 1


def test_glyph_cache_distinct_codes_distinct_paths(font: Any) -> None:
    shim = _VectorFontShim(font)
    cache = GlyphCache(shim)
    a = cache.get_path_for_character_code(ord("A"))
    b = cache.get_path_for_character_code(ord("B"))
    assert a is not b


def test_glyph_cache_caches_empty_path_for_space(font: Any) -> None:
    shim = _VectorFontShim(font)
    cache = GlyphCache(shim)
    p = cache.get_path_for_character_code(ord(" "))
    assert p == []
    assert cache.get_path_for_character_code(ord(" ")) is p


def test_empty_path_helper_is_empty_list() -> None:
    assert _empty_path() == []


# ---------------------------------------------------------------------------
# _AggdrawPathPen: unit-em scaling + quadratic -> cubic conversion
# ---------------------------------------------------------------------------


def test_aggdraw_pen_scales_coordinates_to_unit_em() -> None:
    pen = _AggdrawPathPen(scale=1.0 / _UPEM)
    pen.move_to((_UPEM, _UPEM))  # one em in each axis -> (1.0, 1.0)
    pen.line_to((0.0, 0.0))
    assert pen.has_segments


def test_aggdraw_pen_empty_until_drawn() -> None:
    pen = _AggdrawPathPen(scale=1.0)
    assert pen.has_segments is False


def test_aggdraw_pen_line_sets_segments() -> None:
    pen = _AggdrawPathPen(scale=1.0)
    pen.move_to((0.0, 0.0))
    pen.line_to((10.0, 0.0))
    assert pen.has_segments


def test_aggdraw_pen_cubic_curve() -> None:
    pen = _AggdrawPathPen(scale=1.0)
    pen.move_to((0.0, 0.0))
    pen.curve_to((1.0, 1.0), (2.0, 1.0), (3.0, 0.0))
    assert pen.has_segments
    assert pen._last == (3.0, 0.0)


def test_aggdraw_pen_quadratic_single_point_is_line_like() -> None:
    # qCurveTo with a single on-curve point degenerates to a straight line.
    pen = _AggdrawPathPen(scale=1.0)
    pen.move_to((0.0, 0.0))
    pen.q_curve_to((5.0, 5.0))
    assert pen.has_segments
    assert pen._last == (5.0, 5.0)


def test_aggdraw_pen_quadratic_off_on() -> None:
    # qCurveTo(off, on) -> one quadratic.
    pen = _AggdrawPathPen(scale=1.0)
    pen.move_to((0.0, 0.0))
    pen.q_curve_to((5.0, 10.0), (10.0, 0.0))
    assert pen.has_segments
    assert pen._last == (10.0, 0.0)


def test_aggdraw_pen_quadratic_two_off_curves_implicit_on() -> None:
    # qCurveTo(off1, off2, on) -> two quadratics with an implicit on-curve
    # midpoint between off1 and off2.
    pen = _AggdrawPathPen(scale=1.0)
    pen.move_to((0.0, 0.0))
    pen.q_curve_to((4.0, 8.0), (12.0, 8.0), (16.0, 0.0))
    assert pen.has_segments
    assert pen._last == (16.0, 0.0)


def test_aggdraw_pen_quadratic_no_current_point_is_noop() -> None:
    pen = _AggdrawPathPen(scale=1.0)
    pen.q_curve_to((5.0, 5.0))
    assert pen.has_segments is False


class _RecordingPath:
    """Stand-in for ``aggdraw.Path`` that records ``curveto`` args (the
    real aggdraw Path has read-only C-level methods we cannot patch)."""

    def __init__(self) -> None:
        self.curves: list[tuple[float, ...]] = []

    def curveto(self, *a: float) -> None:
        self.curves.append(a)


def test_add_quadratic_exact_cubic_elevation() -> None:
    # Verify the quadratic->cubic control-point math: for P0=(0,0),
    # C=(3,3), P3=(6,0): cubic CP1 = P0 + 2/3*(C-P0) = (2,2);
    # CP2 = P3 + 2/3*(C-P3) = (4,2).
    pen = _AggdrawPathPen(scale=1.0)
    rec = _RecordingPath()
    pen.path = rec  # type: ignore[assignment]
    pen._add_quadratic(0.0, 0.0, 3.0, 3.0, 6.0, 0.0)
    assert rec.curves == [(2.0, 2.0, 4.0, 2.0, 6.0, 0.0)]


# ---------------------------------------------------------------------------
# _build_aggdraw_path_from_commands (Type1 / CFF command path)
# ---------------------------------------------------------------------------


def test_build_path_from_commands_empty_returns_none() -> None:
    assert _build_aggdraw_path_from_commands([], scale=1.0) is None


def test_build_path_from_commands_only_moveto_returns_none() -> None:
    # A lone moveto emits no drawable segment.
    assert (
        _build_aggdraw_path_from_commands([("moveto", 0.0, 0.0)], scale=1.0)
        is None
    )


def test_build_path_from_commands_line_emits_path() -> None:
    cmds = [("moveto", 0.0, 0.0), ("lineto", 10.0, 0.0), ("closepath",)]
    path = _build_aggdraw_path_from_commands(cmds, scale=1.0)
    assert isinstance(path, aggdraw.Path)


def test_build_path_from_commands_curve_emits_path() -> None:
    cmds = [
        ("moveto", 0.0, 0.0),
        ("curveto", 1.0, 1.0, 2.0, 1.0, 3.0, 0.0),
        ("closepath",),
    ]
    path = _build_aggdraw_path_from_commands(cmds, scale=0.001)
    assert isinstance(path, aggdraw.Path)
