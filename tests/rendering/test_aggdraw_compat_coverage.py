"""Coverage-boost tests for ``pypdfbox.rendering._aggdraw_compat``.

The shim is the renderer's only entry into skia, so every draw path in
the project routes through here.  These tests exercise the branches that
the renderer-facing tests don't reach today:

- ``_normalize_color`` for int, string (known + unknown), 3-tuple,
  4-tuple, opacity override
- ``Pen`` / ``Brush`` constructors with assorted colour specs
- ``Path``: moveto/lineto/curveto/close, fill-type setters, clear,
  append (Path and non-Path argument)
- ``_acquire_surface`` cache-miss and cache-hit paths
- ``Draw.__init__`` for RGBA fast path + non-RGBA conversion path
- ``Draw.setantialias`` flipping the flag
- ``Draw.settransform`` reset (None) + 6-tuple + malformed inputs
- ``Draw.flush`` no-op fast path vs real blit (RGBA, RGB, L modes)
- ``Draw.path`` with even_odd True/False, brush-only, pen-only,
  pen+brush
- ``Draw.polygon`` short-circuit + fill / stroke / both
- ``Draw.line`` with and without pen
- ``Draw.rectangle`` and ``Draw.ellipse`` fill / stroke / both
- ``Draw.symbol`` raising ``NotImplementedError``
- ``Draw._direct`` property
"""

from __future__ import annotations

# Pre-import numpy before coverage instrumentation triggers
# ``pypdfbox`` -> ``imagecodecs`` -> ``numpy`` (under Python 3.14 the
# second numpy import path raises "cannot load module more than once
# per process").  Importing numpy first means the subsequent reload
# attempt is a cache hit.
import numpy as _np_preload  # noqa: F401
import pytest
from PIL import Image

from pypdfbox.rendering import _aggdraw_compat as agg

# ---------------------------------------------------------------------------
# _normalize_color
# ---------------------------------------------------------------------------


def test_normalize_color_int_passthrough() -> None:
    assert agg._normalize_color(0xDEADBEEF) == 0xDEADBEEF


def test_normalize_color_named_string() -> None:
    # "red" -> (255, 0, 0) with default opacity 255 -> ARGB 0xFFFF0000
    assert agg._normalize_color("red") == 0xFFFF0000


def test_normalize_color_unknown_string_defaults_to_black() -> None:
    # Unknown name falls through the dict.get default ((0, 0, 0))
    assert agg._normalize_color("not-a-color") == 0xFF000000


def test_normalize_color_three_tuple_uses_opacity() -> None:
    assert agg._normalize_color((10, 20, 30), opacity=128) == (
        (128 << 24) | (10 << 16) | (20 << 8) | 30
    )


def test_normalize_color_four_tuple_overrides_opacity() -> None:
    # 4-tuple's alpha wins over the opacity kwarg.
    val = agg._normalize_color((1, 2, 3, 64), opacity=255)
    assert val == ((64 << 24) | (1 << 16) | (2 << 8) | 3)


# ---------------------------------------------------------------------------
# Pen / Brush
# ---------------------------------------------------------------------------


def test_pen_stores_color_width_opacity() -> None:
    p = agg.Pen((255, 0, 0), width=2.5, opacity=200)
    assert p.width == 2.5
    assert p.opacity == 200
    # ARGB packed: alpha 200, red 255
    assert (p.color >> 24) & 0xFF == 200


def test_brush_stores_color_and_opacity() -> None:
    b = agg.Brush((0, 128, 64), opacity=99)
    assert b.opacity == 99
    assert (b.color >> 24) & 0xFF == 99


def test_pen_with_int_color() -> None:
    p = agg.Pen(0xFF00FF00)
    assert p.color == 0xFF00FF00


# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------


def test_path_basic_chain() -> None:
    p = agg.Path()
    p.moveto(0, 0)
    p.lineto(10, 0)
    p.curveto(10, 5, 5, 10, 0, 10)
    p.close()
    # No assertion needed beyond not-raising; verify fill type setters.
    p.set_fill_type_even_odd()
    p.set_fill_type_winding()


def test_path_clear_resets() -> None:
    p = agg.Path()
    p.moveto(0, 0)
    p.lineto(5, 5)
    p.clear()
    # After reset the path should be empty.
    assert p._sk.countPoints() == 0


def test_path_append_path() -> None:
    a = agg.Path()
    a.moveto(0, 0)
    a.lineto(1, 1)
    b = agg.Path()
    b.moveto(2, 2)
    b.lineto(3, 3)
    a.append(b)
    # Appending a real Path should add b's points to a.
    assert a._sk.countPoints() >= 4


def test_path_append_non_path_noop() -> None:
    a = agg.Path()
    a.moveto(0, 0)
    pre = a._sk.countPoints()
    a.append("not a path")  # type: ignore[arg-type]
    assert a._sk.countPoints() == pre


# ---------------------------------------------------------------------------
# _acquire_surface
# ---------------------------------------------------------------------------


def test_acquire_surface_cache_miss_then_hit() -> None:
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    state1, reused1 = agg._acquire_surface(img)
    assert reused1 is False
    state2, reused2 = agg._acquire_surface(img)
    assert reused2 is True
    assert state2 is state1


def test_acquire_surface_unknown_mode_promoted_to_rgba() -> None:
    img = Image.new("L", (4, 4), 0)
    state, reused = agg._acquire_surface(img)
    assert reused is False
    # The cached state is bound to mode "RGBA" (since "L" is not in
    # _MODE_TO_COLORTYPE) — subsequent acquire should be a cache hit.
    state2, reused2 = agg._acquire_surface(img)
    assert reused2 is True
    assert state2 is state


# ---------------------------------------------------------------------------
# Draw construction
# ---------------------------------------------------------------------------


def test_draw_init_rgba_skips_conversion() -> None:
    img = Image.new("RGBA", (6, 6), (1, 2, 3, 255))
    d = agg.Draw(img)
    assert d._direct is True
    assert d._dirty is False
    # Pixels seeded from image — first byte is R channel of (1, 2, 3, 255)
    assert d._pixels[0] == 1


def test_draw_init_non_rgba_converts() -> None:
    img = Image.new("RGB", (5, 5), (10, 20, 30))
    d = agg.Draw(img)
    assert d._dirty is False
    # After convert("RGBA") + seed, first pixel R should be 10.
    assert d._pixels[0] == 10
    # Alpha forced to 255 in conversion.
    assert d._pixels[3] == 255


# ---------------------------------------------------------------------------
# setantialias / settransform
# ---------------------------------------------------------------------------


def test_setantialias_toggle() -> None:
    img = Image.new("RGBA", (2, 2))
    d = agg.Draw(img)
    assert d._antialias is True
    d.setantialias(False)
    assert d._antialias is False
    d.setantialias(1)  # truthy -> True
    assert d._antialias is True


def test_settransform_none_resets() -> None:
    img = Image.new("RGBA", (2, 2))
    d = agg.Draw(img)
    d.settransform((2.0, 0.0, 1.0, 0.0, 2.0, 1.0))
    d.settransform(None)
    # After reset the canvas matrix is the identity — getTotalMatrix
    # exposes it via skia's Canvas API.
    mat = d._canvas.getTotalMatrix()
    assert mat.getScaleX() == pytest.approx(1.0)
    assert mat.getTranslateX() == pytest.approx(0.0)


def test_settransform_six_tuple_applied() -> None:
    img = Image.new("RGBA", (2, 2))
    d = agg.Draw(img)
    d.settransform((2.0, 0.0, 5.0, 0.0, 3.0, 7.0))
    mat = d._canvas.getTotalMatrix()
    assert mat.getScaleX() == pytest.approx(2.0)
    assert mat.getScaleY() == pytest.approx(3.0)
    assert mat.getTranslateX() == pytest.approx(5.0)
    assert mat.getTranslateY() == pytest.approx(7.0)


def test_settransform_wrong_length_raises() -> None:
    img = Image.new("RGBA", (2, 2))
    d = agg.Draw(img)
    with pytest.raises(ValueError):
        d.settransform((1.0, 2.0, 3.0))


# ---------------------------------------------------------------------------
# flush
# ---------------------------------------------------------------------------


def test_flush_noop_when_clean() -> None:
    img = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d = agg.Draw(img)
    # No drawing occurred; flush must be a no-op (no exception, dirty
    # stays False).
    d.flush()
    assert d._dirty is False


def test_flush_blits_back_to_rgba_image() -> None:
    img = Image.new("RGBA", (4, 4), (0, 0, 0, 0))
    d = agg.Draw(img)
    d.rectangle((0, 0, 4, 4), brush=agg.Brush((255, 0, 0)))
    assert d._dirty is True
    d.flush()
    assert d._dirty is False
    # Image should now reflect red pixels.
    px = img.getpixel((1, 1))
    assert px[0] == 255 and px[3] == 255


def test_flush_blits_back_to_rgb_image() -> None:
    img = Image.new("RGB", (4, 4), (0, 0, 0))
    d = agg.Draw(img)
    d.rectangle((0, 0, 4, 4), brush=agg.Brush((0, 255, 0)))
    d.flush()
    assert img.getpixel((1, 1))[1] == 255


def test_flush_blits_back_to_l_image() -> None:
    img = Image.new("L", (4, 4), 0)
    d = agg.Draw(img)
    d.rectangle((0, 0, 4, 4), brush=agg.Brush((255, 255, 255)))
    d.flush()
    # White rectangle on L mode -> non-zero luminance.
    assert img.getpixel((1, 1)) > 0


# ---------------------------------------------------------------------------
# path with even_odd
# ---------------------------------------------------------------------------


def _square_path(x0: float, y0: float, x1: float, y1: float) -> agg.Path:
    p = agg.Path()
    p.moveto(x0, y0)
    p.lineto(x1, y0)
    p.lineto(x1, y1)
    p.lineto(x0, y1)
    p.close()
    return p


def test_path_even_odd_fill() -> None:
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    d = agg.Draw(img)
    pth = _square_path(0, 0, 8, 8)
    d.path(pth, brush=agg.Brush((10, 20, 30)), even_odd=True)
    assert d._dirty is True


def test_path_winding_fill_pen_only() -> None:
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    d = agg.Draw(img)
    pth = _square_path(0, 0, 8, 8)
    d.path(pth, pen=agg.Pen((255, 255, 255), width=1.0), even_odd=False)
    assert d._dirty is True


def test_path_no_pen_no_brush_does_nothing() -> None:
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    d = agg.Draw(img)
    pth = _square_path(0, 0, 8, 8)
    d.path(pth)
    assert d._dirty is False


def test_path_pen_and_brush() -> None:
    img = Image.new("RGBA", (8, 8), (0, 0, 0, 0))
    d = agg.Draw(img)
    pth = _square_path(0, 0, 8, 8)
    d.path(
        pth,
        pen=agg.Pen((0, 0, 255), width=1.0),
        brush=agg.Brush((255, 0, 0)),
    )
    assert d._dirty is True


# ---------------------------------------------------------------------------
# polygon / line / rectangle / ellipse
# ---------------------------------------------------------------------------


def test_polygon_short_circuit() -> None:
    img = Image.new("RGBA", (4, 4))
    d = agg.Draw(img)
    d.polygon([0.0, 0.0], brush=agg.Brush((1, 2, 3)))
    assert d._dirty is False


def test_polygon_fill_only() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.polygon([0, 0, 8, 0, 8, 8, 0, 8], brush=agg.Brush((100, 100, 100)))
    assert d._dirty is True


def test_polygon_stroke_only() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.polygon(
        [0, 0, 8, 0, 8, 8, 0, 8],
        pen=agg.Pen((50, 50, 50), width=1.0),
    )
    assert d._dirty is True


def test_polygon_fill_and_stroke() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.polygon(
        [0, 0, 8, 0, 8, 8, 0, 8],
        pen=agg.Pen((50, 50, 50), width=1.0),
        brush=agg.Brush((100, 100, 100)),
    )
    assert d._dirty is True


def test_line_with_pen() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.line((0.0, 0.0, 8.0, 8.0), agg.Pen((255, 0, 0), width=1.0))
    assert d._dirty is True


def test_line_no_pen_noop() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.line((0.0, 0.0, 8.0, 8.0), None)  # type: ignore[arg-type]
    assert d._dirty is False


def test_rectangle_fill_only() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.rectangle((0, 0, 4, 4), brush=agg.Brush((10, 20, 30)))
    assert d._dirty is True


def test_rectangle_stroke_only() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.rectangle((0, 0, 4, 4), pen=agg.Pen((10, 20, 30), width=1.0))
    assert d._dirty is True


def test_rectangle_fill_and_stroke() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.rectangle(
        (0, 0, 4, 4),
        pen=agg.Pen((1, 2, 3), width=1.0),
        brush=agg.Brush((4, 5, 6)),
    )
    assert d._dirty is True


def test_rectangle_no_pen_no_brush_noop() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.rectangle((0, 0, 4, 4))
    assert d._dirty is False


def test_ellipse_fill_only() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.ellipse((0, 0, 4, 4), brush=agg.Brush((10, 20, 30)))
    assert d._dirty is True


def test_ellipse_stroke_only() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.ellipse((0, 0, 4, 4), pen=agg.Pen((10, 20, 30), width=1.0))
    assert d._dirty is True


def test_ellipse_fill_and_stroke() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.ellipse(
        (0, 0, 4, 4),
        pen=agg.Pen((1, 2, 3), width=1.0),
        brush=agg.Brush((4, 5, 6)),
    )
    assert d._dirty is True


def test_ellipse_no_pen_no_brush_noop() -> None:
    img = Image.new("RGBA", (8, 8))
    d = agg.Draw(img)
    d.ellipse((0, 0, 4, 4))
    assert d._dirty is False


# ---------------------------------------------------------------------------
# symbol / accessors
# ---------------------------------------------------------------------------


def test_symbol_raises_not_implemented() -> None:
    img = Image.new("RGBA", (2, 2))
    d = agg.Draw(img)
    with pytest.raises(NotImplementedError):
        d.symbol("M0 0 L1 1")


def test_internal_accessors_expose_state() -> None:
    img = Image.new("RGBA", (3, 3))
    d = agg.Draw(img)
    assert d._row_bytes == 3 * 4
    assert isinstance(d._pixels, bytearray)
    assert d._surface is d._state.surface
    assert d._canvas is d._state.canvas
