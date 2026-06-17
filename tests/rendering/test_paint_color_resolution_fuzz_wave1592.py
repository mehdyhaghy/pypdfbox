"""Fuzz / parity tests for fill / stroke colour resolution — wave 1592.

Exercises the renderer's colour-resolution pipeline: how an ``rg`` / ``RG`` /
``g`` / ``G`` / ``k`` / ``K`` / ``scn`` / ``SCN`` operator turns a component
vector (+ active colour space) into the concrete 8-bit device RGB stored on
the graphics state (``fill_rgb`` for non-stroking, ``stroke_rgb`` for
stroking), and the ``scn`` / ``SCN`` pattern dispatch where the trailing
``/Name`` operand makes the colour a pattern rather than a solid.

The targets are the resolution helpers themselves —
``PDFRenderer._color_components_to_rgb`` (the colour→RGB transform),
``_op_set_fill_rgb`` / ``_op_set_stroke_rgb`` / ``_op_set_fill_gray`` /
``_op_set_fill_cmyk`` and their stroking twins, ``_op_set_fill_color_n`` /
``_op_set_stroke_color_n`` (the ``scn`` / ``SCN`` dispatch), and the
``PageDrawer.get_paint`` bridge. We drive the operators directly and assert on
``fill_rgb`` / ``stroke_rgb`` — the raster backend is out of scope.

Upstream reference: Apache PDFBox 3.0.x
``org.apache.pdfbox.rendering.PageDrawer.getPaint`` / ``applyColor`` and
``org.apache.pdfbox.pdmodel.graphics.color`` (``PDDeviceRGB.toRGB`` /
``PDDeviceGray.toRGB`` / ``PDDeviceCMYK.toRGB`` / ``PDSeparation.toRGB`` /
``PDIndexed.toRGB`` / ``PDColor`` selecting a pattern).
"""

from __future__ import annotations

from typing import Any

import pytest

from pypdfbox.cos import COSFloat, COSInteger, COSName
from pypdfbox.pdmodel import PDDocument
from pypdfbox.pdmodel.graphics.color import (
    PDDeviceCMYK,
    PDDeviceGray,
    PDDeviceRGB,
)
from pypdfbox.rendering import PDFRenderer
from pypdfbox.rendering import pdf_renderer as pr
from pypdfbox.rendering.page_drawer import PageDrawer

# ---------------------------------------------------------------------------
# Harness
# ---------------------------------------------------------------------------


def _make_renderer() -> PDFRenderer:
    doc = PDDocument()
    renderer = PDFRenderer(doc)
    renderer._gs_stack = [pr._GState()]  # noqa: SLF001
    renderer._resources = None  # noqa: SLF001
    return renderer


def _num(v: float) -> Any:
    if isinstance(v, int):
        return COSInteger.get(v)
    return COSFloat(float(v))


def _ops(*vals: float) -> list[Any]:
    return [_num(v) for v in vals]


def _name(s: str) -> COSName:
    return COSName.get_pdf_name(s)


class _FakeParams:
    """Minimal ``PageDrawerParameters`` stand-in: ``PageDrawer.__init__``
    only needs ``get_page`` / ``get_renderer`` / the cheap accessors."""

    def __init__(self, renderer: PDFRenderer) -> None:
        self._renderer = renderer

    def get_page(self) -> Any:
        return None

    def get_renderer(self) -> PDFRenderer:
        return self._renderer

    def is_subsampling_allowed(self) -> bool:
        return False

    def get_destination(self) -> Any:
        return None

    def get_rendering_hints(self) -> Any:
        return None

    def get_image_downscaling_optimization_threshold(self) -> float:
        return 0.0


def _make_drawer(renderer: PDFRenderer) -> PageDrawer:
    return PageDrawer(_FakeParams(renderer))


class _FakeCS:
    """Minimal colour-space stand-in with a configurable ``to_rgb`` so the
    renderer's resolution path can be exercised for Separation / Indexed /
    custom semantics without building a full COS array."""

    def __init__(self, fn: Any, n_components: int = 1) -> None:
        self._fn = fn
        self._n = n_components
        self.calls: list[tuple[float, ...]] = []

    def to_rgb(self, components: Any) -> Any:
        comps = tuple(float(c) for c in components)
        self.calls.append(comps)
        return self._fn(comps)

    def get_number_of_components(self) -> int:
        return self._n


# ---------------------------------------------------------------------------
# Device RGB / Gray / CMYK  (rg / g / k)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("r", "g", "b", "expected"),
    [
        (1.0, 0.0, 0.0, (255, 0, 0)),
        (0.0, 1.0, 0.0, (0, 255, 0)),
        (0.0, 0.0, 1.0, (0, 0, 255)),
        (0.5, 0.5, 0.5, (128, 128, 128)),
        (0.0, 0.0, 0.0, (0, 0, 0)),
        (1.0, 1.0, 1.0, (255, 255, 255)),
    ],
    ids=["red", "green", "blue", "mid", "black", "white"],
)
def test_fill_device_rgb_to_device_bytes(
    r: float, g: float, b: float, expected: tuple[int, int, int]
) -> None:
    rndr = _make_renderer()
    rndr._op_set_fill_rgb(None, _ops(r, g, b))  # noqa: SLF001
    assert rndr._gs.fill_rgb == expected  # noqa: SLF001
    # The stroking colour must be untouched (default black).
    assert rndr._gs.stroke_rgb == (0, 0, 0)  # noqa: SLF001


@pytest.mark.parametrize(
    ("gray", "expected"),
    [
        (0.0, (0, 0, 0)),
        (1.0, (255, 255, 255)),
        (0.5, (128, 128, 128)),
        (0.25, (64, 64, 64)),
    ],
    ids=["g0", "g1", "g05", "g025"],
)
def test_fill_device_gray_replicated(
    gray: float, expected: tuple[int, int, int]
) -> None:
    rndr = _make_renderer()
    rndr._op_set_fill_gray(None, _ops(gray))  # noqa: SLF001
    rgb = rndr._gs.fill_rgb  # noqa: SLF001
    assert rgb == expected
    # Gray replicates to all three channels.
    assert rgb[0] == rgb[1] == rgb[2]


@pytest.mark.parametrize(
    ("c", "m", "y", "k", "expected"),
    [
        # r=(1-c)(1-k); g=(1-m)(1-k); b=(1-y)(1-k)
        (0.0, 0.0, 0.0, 0.0, (255, 255, 255)),
        (1.0, 1.0, 1.0, 0.0, (0, 0, 0)),
        (0.0, 0.0, 0.0, 1.0, (0, 0, 0)),
        (1.0, 0.0, 0.0, 0.0, (0, 255, 255)),
        (0.0, 1.0, 0.0, 0.0, (255, 0, 255)),
        (0.0, 0.0, 1.0, 0.0, (255, 255, 0)),
        (0.0, 0.0, 0.0, 0.5, (128, 128, 128)),
    ],
    ids=["white", "blackink", "blackk", "cyan", "magenta", "yellow", "halfk"],
)
def test_fill_device_cmyk_converted(
    c: float, m: float, y: float, k: float, expected: tuple[int, int, int]
) -> None:
    rndr = _make_renderer()
    rndr._op_set_fill_cmyk(None, _ops(c, m, y, k))  # noqa: SLF001
    assert rndr._gs.fill_rgb == expected  # noqa: SLF001


# ---------------------------------------------------------------------------
# non-stroking vs stroking source
# ---------------------------------------------------------------------------


def test_stroke_color_does_not_touch_fill() -> None:
    rndr = _make_renderer()
    rndr._op_set_stroke_rgb(None, _ops(1.0, 0.0, 0.0))  # noqa: SLF001
    assert rndr._gs.stroke_rgb == (255, 0, 0)  # noqa: SLF001
    assert rndr._gs.fill_rgb == (0, 0, 0)  # noqa: SLF001


def test_fill_and_stroke_independent() -> None:
    rndr = _make_renderer()
    rndr._op_set_fill_rgb(None, _ops(1.0, 0.0, 0.0))  # noqa: SLF001
    rndr._op_set_stroke_rgb(None, _ops(0.0, 0.0, 1.0))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (255, 0, 0)  # noqa: SLF001
    assert rndr._gs.stroke_rgb == (0, 0, 255)  # noqa: SLF001


def test_stroke_gray_and_cmyk_route_to_stroke_rgb() -> None:
    rndr = _make_renderer()
    rndr._op_set_stroke_gray(None, _ops(0.5))  # noqa: SLF001
    assert rndr._gs.stroke_rgb == (128, 128, 128)  # noqa: SLF001
    assert rndr._gs.fill_rgb == (0, 0, 0)  # noqa: SLF001
    rndr._op_set_stroke_cmyk(None, _ops(1.0, 0.0, 0.0, 0.0))  # noqa: SLF001
    assert rndr._gs.stroke_rgb == (0, 255, 255)  # noqa: SLF001


def test_get_paint_bridge_uses_resolver_when_present() -> None:
    rndr = _make_renderer()
    drawer = _make_drawer(rndr)
    rndr._resolve_color_to_rgb = lambda c: ("RESOLVED", c)  # type: ignore[attr-defined]  # noqa: SLF001
    sentinel = object()
    assert drawer.get_paint(sentinel) == ("RESOLVED", sentinel)


def test_get_non_stroking_vs_stroking_paint() -> None:
    rndr = _make_renderer()
    drawer = _make_drawer(rndr)
    rndr._op_set_fill_rgb(None, _ops(1.0, 0.0, 0.0))  # noqa: SLF001
    rndr._op_set_stroke_rgb(None, _ops(0.0, 1.0, 0.0))  # noqa: SLF001
    assert drawer.get_non_stroking_paint() == (255, 0, 0)
    assert drawer.get_stroking_paint() == (0, 255, 0)


# ---------------------------------------------------------------------------
# Separation: tint -> alternate -> RGB
# ---------------------------------------------------------------------------


def test_separation_tint_applied_via_to_rgb() -> None:
    # A Separation that maps tint t -> alternate Gray (1-t) -> RGB.
    sep = _FakeCS(lambda c: (1.0 - c[0], 1.0 - c[0], 1.0 - c[0]), n_components=1)
    rndr = _make_renderer()
    rndr._gs.fill_color_space = sep  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(0.0))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (255, 255, 255)  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(1.0))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (0, 0, 0)  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(0.5))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (128, 128, 128)  # noqa: SLF001
    # The tint component (not a fixed value) actually reached the CS.
    assert sep.calls[-1] == (0.5,)


def test_separation_stroke_uses_stroke_color_space() -> None:
    sep = _FakeCS(lambda c: (c[0], 0.0, 0.0), n_components=1)
    rndr = _make_renderer()
    rndr._gs.stroke_color_space = sep  # noqa: SLF001
    rndr._op_set_stroke_color_n(None, _ops(1.0))  # noqa: SLF001
    assert rndr._gs.stroke_rgb == (255, 0, 0)  # noqa: SLF001
    assert rndr._gs.fill_rgb == (0, 0, 0)  # noqa: SLF001


def test_separation_to_rgb_failure_leaves_color_unchanged() -> None:
    # to_rgb returns None (conversion failed) -> fill_rgb stays at default.
    sep = _FakeCS(lambda c: None, n_components=1)
    rndr = _make_renderer()
    rndr._gs.fill_color_space = sep  # noqa: SLF001
    rndr._gs.fill_rgb = (10, 20, 30)  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(0.7))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (10, 20, 30)  # noqa: SLF001


# ---------------------------------------------------------------------------
# Indexed: palette lookup
# ---------------------------------------------------------------------------


def test_indexed_palette_lookup() -> None:
    palette = {0: (10, 20, 30), 1: (255, 0, 0), 2: (0, 255, 0)}

    def lookup(c: tuple[float, ...]) -> tuple[float, float, float]:
        r, g, b = palette[int(c[0])]
        return (r / 255.0, g / 255.0, b / 255.0)

    idx = _FakeCS(lookup, n_components=1)
    rndr = _make_renderer()
    rndr._gs.fill_color_space = idx  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(1))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (255, 0, 0)  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(2))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (0, 255, 0)  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(0))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (10, 20, 30)  # noqa: SLF001


# ---------------------------------------------------------------------------
# Pattern dispatch: fill becomes a pattern, not a solid
# ---------------------------------------------------------------------------


def _renderer_with_pattern(name: str, pattern_obj: Any) -> PDFRenderer:
    class _Res:
        def get_pattern(self, n: Any) -> Any:
            return pattern_obj if n.name == name else None

        def get_color_space(self, n: Any) -> Any:
            return None

    rndr = _make_renderer()
    rndr._resources = _Res()  # noqa: SLF001
    return rndr


def test_pattern_fill_sets_pattern_not_solid() -> None:
    pat = object()
    rndr = _renderer_with_pattern("P0", pat)
    rndr._gs.fill_rgb = (5, 5, 5)  # noqa: SLF001
    rndr._op_set_fill_color_n(None, [_name("P0")])  # noqa: SLF001
    assert rndr._gs.fill_pattern is pat  # noqa: SLF001
    # Solid fill_rgb is left as-is (the pattern paints its own colours).
    assert rndr._gs.fill_rgb == (5, 5, 5)  # noqa: SLF001
    # No tint for a colored (Type 1) pattern — only the name was supplied.
    assert rndr._gs.fill_pattern_tint is None  # noqa: SLF001


def test_pattern_stroke_sets_stroke_pattern() -> None:
    pat = object()
    rndr = _renderer_with_pattern("P1", pat)
    rndr._op_set_stroke_color_n(None, [_name("P1")])  # noqa: SLF001
    assert rndr._gs.stroke_pattern is pat  # noqa: SLF001
    assert rndr._gs.fill_pattern is None  # noqa: SLF001


def test_uncolored_pattern_tint_resolved_via_underlying() -> None:
    # Uncolored tiling pattern (PaintType 2): leading N components are the
    # tint, resolved through the Pattern CS's underlying space.
    pat = object()
    under = _FakeCS(lambda c: (c[0], c[0], c[0]), n_components=1)

    class _PatternCS:
        def get_underlying_color_space(self) -> Any:
            return under

    rndr = _renderer_with_pattern("P2", pat)
    rndr._gs.fill_color_space = _PatternCS()  # noqa: SLF001
    rndr._op_set_fill_color_n(  # noqa: SLF001
        None, [_num(1.0), _name("P2")]
    )
    assert rndr._gs.fill_pattern is pat  # noqa: SLF001
    assert rndr._gs.fill_pattern_tint == (255, 255, 255)  # noqa: SLF001
    assert under.calls[-1] == (1.0,)


def test_pattern_only_zero_components_no_tint() -> None:
    # Only a /Name operand (0 numeric components) -> tint is None.
    pat = object()
    rndr = _renderer_with_pattern("P3", pat)
    rndr._op_set_fill_color_n(None, [_name("P3")])  # noqa: SLF001
    assert rndr._gs.fill_pattern is pat  # noqa: SLF001
    assert rndr._gs.fill_pattern_tint is None  # noqa: SLF001


def test_reselecting_pattern_cs_keeps_active_pattern() -> None:
    # Established invariant (waves 391 / 511 / 601): re-selecting the
    # Pattern CS does NOT clear an already-selected pattern — only switching
    # to a non-Pattern CS does. The Pattern CS's "initial colour" reset is a
    # no-op for the pattern slot here.
    pat = object()
    rndr = _renderer_with_pattern("P5", pat)
    rndr._op_set_fill_color_space(None, [_name("Pattern")])  # noqa: SLF001
    rndr._op_set_fill_color_n(None, [_name("P5")])  # noqa: SLF001
    assert rndr._gs.fill_pattern is pat  # noqa: SLF001
    # Re-selecting the Pattern CS keeps the active pattern.
    rndr._op_set_fill_color_space(None, [_name("Pattern")])  # noqa: SLF001
    assert rndr._gs.fill_pattern is pat  # noqa: SLF001
    # Switching to a concrete (non-Pattern) CS clears it.
    rndr._op_set_fill_color_space(None, [_name("DeviceRGB")])  # noqa: SLF001
    assert rndr._gs.fill_pattern is None  # noqa: SLF001


def test_reselecting_stroke_pattern_cs_keeps_active_pattern() -> None:
    pat = object()
    rndr = _renderer_with_pattern("P6", pat)
    rndr._op_set_stroke_color_space(None, [_name("Pattern")])  # noqa: SLF001
    rndr._op_set_stroke_color_n(None, [_name("P6")])  # noqa: SLF001
    assert rndr._gs.stroke_pattern is pat  # noqa: SLF001
    rndr._op_set_stroke_color_space(None, [_name("Pattern")])  # noqa: SLF001
    assert rndr._gs.stroke_pattern is pat  # noqa: SLF001
    rndr._op_set_stroke_color_space(None, [_name("DeviceRGB")])  # noqa: SLF001
    assert rndr._gs.stroke_pattern is None  # noqa: SLF001


def test_switching_from_pattern_back_to_solid_clears_pattern() -> None:
    pat = object()
    rndr = _renderer_with_pattern("P4", pat)
    rndr._op_set_fill_color_n(None, [_name("P4")])  # noqa: SLF001
    assert rndr._gs.fill_pattern is pat  # noqa: SLF001
    # Now a numeric scn (DeviceRGB default for 3 comps) clears the pattern.
    rndr._gs.fill_color_space = PDDeviceRGB.INSTANCE  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(1.0, 0.0, 0.0))  # noqa: SLF001
    assert rndr._gs.fill_pattern is None  # noqa: SLF001
    assert rndr._gs.fill_rgb == (255, 0, 0)  # noqa: SLF001


# ---------------------------------------------------------------------------
# Clamping to [0, 255]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("over", "expected"),
    [
        (2.0, (255, 255, 255)),
        (-1.0, (0, 0, 0)),
        (1.5, (255, 255, 255)),
        (-0.0001, (0, 0, 0)),
    ],
    ids=["over2", "negfull", "over15", "tinyneg"],
)
def test_out_of_range_components_clamped(
    over: float, expected: tuple[int, int, int]
) -> None:
    cs = _FakeCS(lambda c: (over, over, over), n_components=1)
    rndr = _make_renderer()
    rndr._gs.fill_color_space = cs  # noqa: SLF001
    rndr._op_set_fill_color_n(None, _ops(0.5))  # noqa: SLF001
    assert rndr._gs.fill_rgb == expected  # noqa: SLF001


def test_device_rgb_out_of_range_clamped() -> None:
    rndr = _make_renderer()
    rndr._op_set_fill_rgb(None, _ops(2.0, -1.0, 0.5))  # noqa: SLF001
    assert rndr._gs.fill_rgb == (255, 0, 128)  # noqa: SLF001


# ---------------------------------------------------------------------------
# _color_components_to_rgb direct: default-CS-by-arity dispatch
# ---------------------------------------------------------------------------


def test_components_to_rgb_default_cs_by_arity() -> None:
    rndr = _make_renderer()
    # 1 comp with no CS -> DeviceGray.
    assert rndr._color_components_to_rgb((0.5,), None) == (128, 128, 128)  # noqa: SLF001
    # 3 comps with no CS -> DeviceRGB.
    assert rndr._color_components_to_rgb(  # noqa: SLF001
        (1.0, 0.0, 0.0), None
    ) == (255, 0, 0)
    # 4 comps with no CS -> DeviceCMYK.
    assert rndr._color_components_to_rgb(  # noqa: SLF001
        (0.0, 0.0, 0.0, 0.0), None
    ) == (255, 255, 255)
    # 2 comps with no CS -> no default -> None.
    assert rndr._color_components_to_rgb((0.5, 0.5), None) is None  # noqa: SLF001


def test_components_to_rgb_uses_explicit_device_singletons() -> None:
    rndr = _make_renderer()
    assert rndr._color_components_to_rgb(  # noqa: SLF001
        (0.25,), PDDeviceGray.INSTANCE
    ) == (64, 64, 64)
    assert rndr._color_components_to_rgb(  # noqa: SLF001
        (0.0, 1.0, 0.0), PDDeviceRGB.INSTANCE
    ) == (0, 255, 0)
    assert rndr._color_components_to_rgb(  # noqa: SLF001
        (1.0, 0.0, 0.0, 0.0), PDDeviceCMYK.INSTANCE
    ) == (0, 255, 255)


def test_components_to_rgb_short_output_returns_none() -> None:
    # A to_rgb that returns < 3 channels is rejected (None), not padded.
    cs = _FakeCS(lambda c: (0.5,), n_components=1)
    rndr = _make_renderer()
    assert rndr._color_components_to_rgb((0.3,), cs) is None  # noqa: SLF001


def test_components_to_rgb_exception_returns_none() -> None:
    def boom(c: tuple[float, ...]) -> Any:
        raise ValueError("nope")

    cs = _FakeCS(boom, n_components=1)
    rndr = _make_renderer()
    assert rndr._color_components_to_rgb((0.3,), cs) is None  # noqa: SLF001
