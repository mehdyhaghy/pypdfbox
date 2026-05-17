"""Aggdraw-compatible shim backed by skia-python.

Wave 1329 replaced the unmaintained ``aggdraw`` C extension (stale since
March 2020) with ``skia-python`` (Google's 2D engine — same renderer as
Chrome / Flutter / Android, BSD-3-Clause).  Skia is a strict upgrade over
AGG for our renderer: better anti-aliasing, native cubic-Bezier curves
(no quadratic approximation), and active upstream maintenance.

This module preserves the *exact* aggdraw class/method surface used by
``pypdfbox.rendering`` so the migration is import-only.  The audited
surface is small — only four classes and a handful of methods:

    classes  : Draw, Path, Pen, Brush
    Draw     : setantialias, settransform, flush, path
    Path     : moveto, lineto, curveto, close
    Pen      : Pen(rgb_tuple, width=...)
    Brush    : Brush(rgb_tuple)

A few rare methods (``Path.clear``, ``Path.append``, ``Draw.symbol``,
``Draw.polygon`` / ``rectangle`` / ``line`` / ``ellipse``) are *not*
called on aggdraw objects in the codebase today (a ``grep`` audit ran in
wave 1329 confirmed this — those names that do appear belong to
``PIL.ImageDraw.Draw`` instances).  We still implement stubs for the
Path/Draw vocabulary in case future ports lean on them.
"""

from __future__ import annotations

from typing import Any

import skia
from PIL import Image as _PILImage

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------


def _normalize_color(color: Any, opacity: int = 255) -> int:
    """Convert an aggdraw colour spec to a skia ARGB int.

    aggdraw accepted ``(r, g, b)`` or ``(r, g, b, a)`` tuples plus a
    separate ``opacity`` keyword (0..255).  skia uses a packed 32-bit
    ARGB int, which is what ``skia.Paint(Color=...)`` expects.
    """
    if isinstance(color, int):
        return color
    if isinstance(color, str):
        # Aggdraw also accepted CSS-like strings such as "black".  The
        # renderer never passes strings, but be defensive.
        named = {
            "black": (0, 0, 0),
            "white": (255, 255, 255),
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
        }
        color = named.get(color.lower(), (0, 0, 0))
    r, g, b, *rest = color
    a = int(rest[0]) if rest else int(opacity)
    return skia.ColorSetARGB(a & 0xFF, int(r) & 0xFF, int(g) & 0xFF, int(b) & 0xFF)


# ---------------------------------------------------------------------------
# Pen / Brush
# ---------------------------------------------------------------------------


class Pen:
    """``aggdraw.Pen(color, width=1.0, opacity=255)`` stand-in.

    Stored as plain attributes; consumed by :class:`Draw` when stroking.
    """

    __slots__ = ("color", "width", "opacity")

    def __init__(self, color: Any, width: float = 1.0, opacity: int = 255) -> None:
        self.color: int = _normalize_color(color, opacity)
        self.width: float = float(width)
        self.opacity: int = int(opacity)


class Brush:
    """``aggdraw.Brush(color, opacity=255)`` stand-in (fill paint)."""

    __slots__ = ("color", "opacity")

    def __init__(self, color: Any, opacity: int = 255) -> None:
        self.color: int = _normalize_color(color, opacity)
        self.opacity: int = int(opacity)


# ---------------------------------------------------------------------------
# Path
# ---------------------------------------------------------------------------


class Path:
    """``aggdraw.Path()`` stand-in — thin wrapper over ``skia.Path``.

    The aggdraw API is build-then-draw: callers chain ``moveto`` /
    ``lineto`` / ``curveto`` / ``close`` and then hand the path to
    ``Draw.path``.  We keep a live ``skia.Path`` instance and forward
    operations to it.
    """

    __slots__ = ("_sk",)

    def __init__(self) -> None:
        self._sk = skia.Path()

    def moveto(self, x: float, y: float) -> None:
        self._sk.moveTo(float(x), float(y))

    def lineto(self, x: float, y: float) -> None:
        self._sk.lineTo(float(x), float(y))

    def curveto(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        x3: float,
        y3: float,
    ) -> None:
        # aggdraw ``curveto`` is a cubic Bezier — same semantics as
        # ``skia.Path.cubicTo`` (no degree mismatch, no approximation).
        self._sk.cubicTo(
            float(x1), float(y1), float(x2), float(y2), float(x3), float(y3),
        )

    def close(self) -> None:
        self._sk.close()

    # The following two are not currently invoked anywhere in pypdfbox,
    # but they appear in the aggdraw public API and may be needed if
    # future ports use them.  Implemented as best-effort stubs.

    def clear(self) -> None:
        """Reset the path to empty (aggdraw.Path.clear)."""
        self._sk.reset()

    def append(self, other: Path) -> None:
        """Concatenate another :class:`Path` onto this one."""
        if isinstance(other, Path):
            self._sk.addPath(other._sk)


# ---------------------------------------------------------------------------
# Draw
# ---------------------------------------------------------------------------


# Map PIL image modes to (skia.ColorType, channels-per-pixel).  Only RGB
# and RGBA are exercised by the renderer; we still register a couple of
# others in case a future caller passes them.
_MODE_TO_COLORTYPE = {
    "RGBA": (skia.kRGBA_8888_ColorType, 4),
    "RGB": (skia.kRGBA_8888_ColorType, 4),  # promoted to RGBA internally
    "RGBX": (skia.kRGBA_8888_ColorType, 4),
}


class Draw:
    """``aggdraw.Draw(pil_image)`` stand-in.

    The contract preserved from aggdraw is:

      1. ``Draw(image)`` wraps a PIL image as a drawable surface.
      2. ``setantialias`` / ``settransform`` / ``path`` mutate state.
      3. ``flush()`` makes the PIL image reflect the rendered pixels.

    Skia anti-aliasing is configured *per-paint*, not per-canvas, so the
    ``setantialias`` flag is recorded and applied to every paint we
    build (defaulting to ``True``, which matches how the renderer was
    using aggdraw in practice).
    """

    def __init__(self, image: _PILImage.Image) -> None:
        self._pil = image
        self._antialias = True
        # We always work in an RGBA scratch buffer so skia has a uniform
        # ColorType to render into.  On ``flush`` the buffer is blitted
        # back to the original PIL image, preserving its mode.
        self._mode = image.mode if image.mode in _MODE_TO_COLORTYPE else "RGBA"
        self._size = image.size
        # Seed the skia buffer with the PIL pixels so subsequent draws
        # are composited on top of existing content (matches aggdraw's
        # behaviour — the canvas is not cleared on wrap).
        rgba = image.convert("RGBA")
        self._pixels = bytearray(rgba.tobytes())
        info = skia.ImageInfo.Make(
            self._size[0],
            self._size[1],
            skia.kRGBA_8888_ColorType,
            skia.kUnpremul_AlphaType,
        )
        self._row_bytes = self._size[0] * 4
        self._surface = skia.Surface.MakeRasterDirect(
            info, self._pixels, self._row_bytes,
        )
        if self._surface is None:
            # Fall back to a managed raster surface — pixels will be
            # read back via readPixels on flush.
            self._surface = skia.Surface(self._size[0], self._size[1])
            self._direct = False
        else:
            self._direct = True
        self._canvas = self._surface.getCanvas()

    # ---- state ----------------------------------------------------------

    def setantialias(self, on: bool) -> None:  # noqa: FBT001 - aggdraw signature
        """Record AA flag.  skia AA is per-Paint; we apply it on draw."""
        self._antialias = bool(on)

    def settransform(self, matrix6: tuple[float, ...] | None = None) -> None:
        """Apply (or reset) the canvas affine transform.

        aggdraw / PIL use the row-vector affine convention

            x' = a*x + b*y + c
            y' = d*x + e*y + f

        i.e. ``(a, b, c, d, e, f)`` = ``(scaleX, skewX, transX, skewY,
        scaleY, transY)``.  skia.Matrix.MakeAll takes those six in the
        same order followed by the perspective row ``(0, 0, 1)``.
        """
        if matrix6 is None:
            self._canvas.resetMatrix()
            return
        a, b, c, d, e, f = matrix6
        m = skia.Matrix.MakeAll(a, b, c, d, e, f, 0, 0, 1)
        self._canvas.setMatrix(m)

    # ---- drawing --------------------------------------------------------

    def _make_fill_paint(self, color: int) -> skia.Paint:
        return skia.Paint(
            Color=color,
            Style=skia.Paint.kFill_Style,
            AntiAlias=self._antialias,
        )

    def _make_stroke_paint(self, color: int, width: float) -> skia.Paint:
        return skia.Paint(
            Color=color,
            StrokeWidth=width,
            Style=skia.Paint.kStroke_Style,
            AntiAlias=self._antialias,
        )

    def path(
        self,
        path: Path,
        pen: Pen | None = None,
        brush: Brush | None = None,
    ) -> None:
        """Stroke and/or fill ``path``.

        aggdraw's call convention is ``draw.path(path, pen, brush)`` —
        ``pen`` may be ``None`` for fill-only, ``brush`` may be ``None``
        for stroke-only.  Fill is rendered first so the stroke sits on
        top (matches aggdraw and standard PDF semantics).
        """
        sk_path = path._sk
        if brush is not None:
            self._canvas.drawPath(sk_path, self._make_fill_paint(brush.color))
        if pen is not None:
            self._canvas.drawPath(
                sk_path, self._make_stroke_paint(pen.color, pen.width),
            )

    # The remaining methods below are NOT exercised by the renderer at
    # the time of porting (the audit in wave 1329 confirmed it), but
    # they're part of the aggdraw public API and the implementation is
    # cheap, so include them for forward-compatibility.

    def polygon(
        self,
        xy_list: list[float],
        pen: Pen | None = None,
        brush: Brush | None = None,
    ) -> None:
        if len(xy_list) < 4:
            return
        p = skia.Path()
        p.moveTo(float(xy_list[0]), float(xy_list[1]))
        for i in range(2, len(xy_list), 2):
            p.lineTo(float(xy_list[i]), float(xy_list[i + 1]))
        p.close()
        if brush is not None:
            self._canvas.drawPath(p, self._make_fill_paint(brush.color))
        if pen is not None:
            self._canvas.drawPath(
                p, self._make_stroke_paint(pen.color, pen.width),
            )

    def line(self, xy: tuple[float, float, float, float], pen: Pen) -> None:
        if pen is None:
            return
        self._canvas.drawLine(
            float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3]),
            self._make_stroke_paint(pen.color, pen.width),
        )

    def rectangle(
        self,
        xy: tuple[float, float, float, float],
        pen: Pen | None = None,
        brush: Brush | None = None,
    ) -> None:
        rect = skia.Rect.MakeLTRB(
            float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3]),
        )
        if brush is not None:
            self._canvas.drawRect(rect, self._make_fill_paint(brush.color))
        if pen is not None:
            self._canvas.drawRect(
                rect, self._make_stroke_paint(pen.color, pen.width),
            )

    def ellipse(
        self,
        xy: tuple[float, float, float, float],
        pen: Pen | None = None,
        brush: Brush | None = None,
    ) -> None:
        rect = skia.Rect.MakeLTRB(
            float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3]),
        )
        if brush is not None:
            self._canvas.drawOval(rect, self._make_fill_paint(brush.color))
        if pen is not None:
            self._canvas.drawOval(
                rect, self._make_stroke_paint(pen.color, pen.width),
            )

    def symbol(self, *_args: Any, **_kwargs: Any) -> None:
        """No-op stub.

        ``aggdraw.symbol`` is a tiny SVG-path renderer that no callsite
        in pypdfbox exercises.  Rather than pull in a partial SVG
        parser, leave it as a documented no-op; raise if anyone ever
        relies on it so the failure is loud.
        """
        raise NotImplementedError(
            "aggdraw.Draw.symbol() is not implemented in the skia shim; "
            "no callsite in pypdfbox uses it. Add an implementation here "
            "if a future port needs it.",
        )

    # ---- flush ----------------------------------------------------------

    def flush(self) -> None:
        """Commit pending draws and blit pixels back to the PIL image."""
        # Force any pending GPU/CPU work to materialise in the backing
        # buffer.  For raster surfaces this is essentially a no-op but
        # we call it for parity with future GPU-backed surfaces.
        self._surface.flushAndSubmit()

        if self._direct:
            # ``_pixels`` was handed to skia via MakeRasterDirect, so it
            # already holds the rendered RGBA bytes.
            rgba_bytes = bytes(self._pixels)
        else:
            # Managed raster path: snapshot + readback.
            snap = self._surface.makeImageSnapshot()
            info = skia.ImageInfo.Make(
                self._size[0],
                self._size[1],
                skia.kRGBA_8888_ColorType,
                skia.kUnpremul_AlphaType,
            )
            out = bytearray(self._size[0] * self._size[1] * 4)
            snap.readPixels(info, out, self._row_bytes, 0, 0)
            rgba_bytes = bytes(out)

        rendered = _PILImage.frombytes("RGBA", self._size, rgba_bytes)
        # Convert back to the PIL image's original mode and paste in
        # place so callers that still hold a reference see the update.
        if self._pil.mode == "RGBA":
            self._pil.paste(rendered)
        elif self._pil.mode == "RGB":
            self._pil.paste(rendered.convert("RGB"))
        else:
            self._pil.paste(rendered.convert(self._pil.mode))


__all__ = ["Brush", "Draw", "Path", "Pen"]
