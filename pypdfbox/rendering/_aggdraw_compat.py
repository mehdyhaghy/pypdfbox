"""Aggdraw-compatible shim backed by skia-python.

Wave 1329 replaced the unmaintained ``aggdraw`` C extension (stale since
March 2020) with ``skia-python`` (Google's 2D engine — same renderer as
Chrome / Flutter / Android, BSD-3-Clause).  Skia is a strict upgrade over
AGG for our renderer: better anti-aliasing, native cubic-Bezier curves
(no quadratic approximation), and active upstream maintenance.

Wave 1330B trimmed the shim's internal copies so a fresh
``Draw(pil_image)`` is a near-zero cost wrap rather than a paint-and-
copy:

  * for the common ``mode="RGBA"`` PIL image we skip the
    ``convert("RGBA")`` allocation (the source is already RGBA);
  * the skia raster surface is wired straight at our backing
    ``bytearray`` via ``skia.Surface.MakeRasterDirect`` so canvas writes
    land in our buffer with no intermediate copy;
  * a ``_dirty`` flag means ``flush()`` is a no-op when no drawing
    happened since the last flush (the renderer often binds + flushes a
    fresh ``Draw`` purely to refresh the skia view after a PIL paste);
  * the shim now exposes even-odd fills natively via
    :meth:`Path.set_fill_type_even_odd` (skia ``PathFillType.kEvenOdd``)
    so the renderer no longer needs the PIL-mask fallback for it.

The class/method surface is kept identical to upstream aggdraw — the
audited surface is small:

    classes  : Draw, Path, Pen, Brush
    Draw     : setantialias, settransform, flush, path
    Path     : moveto, lineto, curveto, close, set_fill_type_even_odd
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

    Beyond aggdraw's colour + width surface, the skia shim accepts the
    optional PDF stroke-style attributes so the renderer can plumb the
    ``J`` / ``j`` / ``M`` / ``d`` graphics-state through to skia's
    ``Paint`` (cap / join / miter) and ``DashPathEffect`` (dash):

    * ``line_cap``   — 0 butt, 1 round, 2 projecting-square (PDF §8.4.3.3)
    * ``line_join``  — 0 miter, 1 round, 2 bevel (PDF §8.4.3.4)
    * ``miter_limit``— positive ratio (PDF §8.4.3.5)
    * ``dash``       — ``(intervals_tuple, phase)`` in the same coordinate
      space as the path, or ``None`` for a solid line (PDF §8.4.3.6)

    aggdraw never carried any of these, so they default to spec defaults
    (butt / miter / 10.0 / solid) and are pure additive extensions.
    """

    __slots__ = (
        "color",
        "dash",
        "line_cap",
        "line_join",
        "miter_limit",
        "opacity",
        "width",
    )

    def __init__(
        self,
        color: Any,
        width: float = 1.0,
        opacity: int = 255,
        *,
        line_cap: int = 0,
        line_join: int = 0,
        miter_limit: float = 10.0,
        dash: tuple[tuple[float, ...], float] | None = None,
    ) -> None:
        self.color: int = _normalize_color(color, opacity)
        self.width: float = float(width)
        self.opacity: int = int(opacity)
        self.line_cap: int = int(line_cap)
        self.line_join: int = int(line_join)
        self.miter_limit: float = float(miter_limit)
        self.dash: tuple[tuple[float, ...], float] | None = dash


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

    # ---- fill-rule (wave 1330B) ----------------------------------------

    def set_fill_type_even_odd(self) -> None:
        """Mark the path as even-odd filled (PDF ``f*`` / ``B*`` / ``b*``).

        Skia's path fill type is honoured natively by ``drawPath`` so
        the renderer no longer needs the PIL-mask fallback that used to
        rasterise + composite by hand.  Aggdraw had no even-odd support,
        which is why this method has no aggdraw counterpart.
        """
        self._sk.setFillType(skia.PathFillType.kEvenOdd)

    def set_fill_type_winding(self) -> None:
        """Reset to non-zero winding (PDF default — ``f`` / ``B`` / ``b``).

        Skia's default is ``kWinding``; this is provided for symmetry so
        a cached path can be reused for both fill rules without leaking
        state.
        """
        self._sk.setFillType(skia.PathFillType.kWinding)

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

# Attribute name used on PIL images to memo-ise the most recently built
# skia state so successive ``Draw(image)`` calls on the same image can
# skip the surface + bytearray rebuild.  The renderer rebinds ``Draw``
# dozens of times per page (after every ``image.paste``), so this is the
# hot path.  Stored on the image's ``__dict__`` because PIL images are
# regular Python objects.
_SKIA_STATE_ATTR = "_pypdfbox_skia_state"


class _CachedSurface:
    """Per-image cache: skia surface + the bytearray it renders into.

    The bytearray is the ground truth — ``Draw`` writes through skia
    into it, and ``flush`` writes it back to the PIL image.  Keeping it
    pinned to the image means a ``Draw(image)`` rebind only has to
    re-seed the bytearray from the (possibly externally mutated) image
    pixels rather than re-allocating both the bytearray and a fresh
    skia surface.
    """

    __slots__ = ("canvas", "mode", "pixels", "row_bytes", "size", "surface")

    def __init__(self, size: tuple[int, int], mode: str) -> None:
        self.size = size
        self.mode = mode
        width, height = size
        self.row_bytes = width * 4
        self.pixels = bytearray(width * height * 4)
        info = skia.ImageInfo.Make(
            width,
            height,
            skia.kRGBA_8888_ColorType,
            skia.kUnpremul_AlphaType,
        )
        surface = skia.Surface.MakeRasterDirect(
            info, self.pixels, self.row_bytes,
        )
        if surface is None:  # pragma: no cover - skia always succeeds
            surface = skia.Surface(width, height)
        self.surface = surface
        self.canvas = surface.getCanvas()


def _acquire_surface(image: _PILImage.Image) -> tuple[_CachedSurface, bool]:
    """Return a skia surface bound to ``image``, reusing the per-image
    cache when possible.

    The second element is ``True`` when the cache was reused (caller can
    skip the constructor-time seed if it knows the bytearray already
    reflects the image's current pixels — see :class:`Draw`).
    """
    mode = image.mode if image.mode in _MODE_TO_COLORTYPE else "RGBA"
    cached = image.__dict__.get(_SKIA_STATE_ATTR)
    if (
        isinstance(cached, _CachedSurface)
        and cached.size == image.size
        and cached.mode == mode
    ):
        return cached, True
    state = _CachedSurface(image.size, mode)
    image.__dict__[_SKIA_STATE_ATTR] = state
    return state, False


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

    Wave 1330B: the surface + backing bytearray live on the PIL image
    itself (see :func:`_acquire_surface`).  A rebind of ``Draw`` on the
    same image therefore reuses the same skia surface — only the
    bytearray needs to be re-seeded from the image's (possibly
    externally pasted) pixels.  An RGBA image skips even the
    ``convert("RGBA")`` allocation.  A ``flush()`` with no intervening
    draw is a no-op.
    """

    def __init__(self, image: _PILImage.Image) -> None:
        self._pil = image
        self._antialias = True
        # We always work in an RGBA scratch buffer so skia has a uniform
        # ColorType to render into.  On ``flush`` the buffer is blitted
        # back to the original PIL image, preserving its mode.
        self._mode = image.mode if image.mode in _MODE_TO_COLORTYPE else "RGBA"
        self._size = image.size
        state, _reused = _acquire_surface(image)
        self._state = state
        # Seed the bytearray with the image's current RGBA pixels so
        # subsequent draws composite over existing content (matches
        # aggdraw's behaviour — the canvas is not cleared on wrap).
        # The common case is mode="RGBA" — skip the conversion copy.
        rgba_bytes = (
            image.tobytes()
            if image.mode == "RGBA"
            else image.convert("RGBA").tobytes()
        )
        state.pixels[:] = rgba_bytes
        # No draw operations have happened yet — flush() is a no-op
        # until the caller actually paints something.
        self._dirty = False

    # ---- internal accessors --------------------------------------------

    @property
    def _surface(self) -> skia.Surface:
        return self._state.surface

    @property
    def _canvas(self) -> skia.Canvas:
        return self._state.canvas

    @property
    def _pixels(self) -> bytearray:
        return self._state.pixels

    @property
    def _row_bytes(self) -> int:
        return self._state.row_bytes

    # ``_direct`` historically reported whether MakeRasterDirect
    # succeeded.  The cache helper now always uses MakeRasterDirect on
    # the happy path; expose the attribute for any test that still
    # inspects it.
    @property
    def _direct(self) -> bool:
        return True

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
        canvas = self._canvas
        if matrix6 is None:
            canvas.resetMatrix()
            return
        a, b, c, d, e, f = matrix6
        # MakeAll constructs the matrix in place — no intermediate
        # PIL.Image.transform round-trip; just a struct-init.
        canvas.setMatrix(skia.Matrix.MakeAll(a, b, c, d, e, f, 0.0, 0.0, 1.0))

    # ---- drawing --------------------------------------------------------

    def _make_fill_paint(self, color: int) -> skia.Paint:
        return skia.Paint(
            Color=color,
            Style=skia.Paint.kFill_Style,
            AntiAlias=self._antialias,
        )

    # PDF cap / join code → skia enum. PDF 32000-1 §8.4.3.3 / §8.4.3.4.
    _CAP = {
        0: skia.Paint.Cap.kButt_Cap,
        1: skia.Paint.Cap.kRound_Cap,
        2: skia.Paint.Cap.kSquare_Cap,
    }
    _JOIN = {
        0: skia.Paint.Join.kMiter_Join,
        1: skia.Paint.Join.kRound_Join,
        2: skia.Paint.Join.kBevel_Join,
    }

    def _make_stroke_paint(self, color: int, width: float) -> skia.Paint:
        return skia.Paint(
            Color=color,
            StrokeWidth=width,
            Style=skia.Paint.kStroke_Style,
            AntiAlias=self._antialias,
        )

    def _make_stroke_paint_from_pen(self, pen: Pen) -> skia.Paint:
        """Build a stroke :class:`skia.Paint` honouring the pen's PDF
        line-style attributes (cap / join / miter / dash).

        Cap and join map straight onto skia's ``StrokeCap`` / ``StrokeJoin``;
        the miter limit onto ``StrokeMiter``. A dash pattern is realised via
        ``skia.DashPathEffect`` — skia requires an even-length intervals
        array, so an odd-length PDF dash array is duplicated (``[a] -> [a,
        a]``) to mean "a on, a off", matching the PDF rule that a single-
        element array applies the same length to gaps. Degenerate dash
        arrays (sum <= 0) are skipped so the line stays solid rather than
        vanishing.
        """
        paint = skia.Paint(
            Color=pen.color,
            StrokeWidth=pen.width,
            Style=skia.Paint.kStroke_Style,
            AntiAlias=self._antialias,
        )
        paint.setStrokeCap(self._CAP.get(pen.line_cap, skia.Paint.Cap.kButt_Cap))
        paint.setStrokeJoin(
            self._JOIN.get(pen.line_join, skia.Paint.Join.kMiter_Join)
        )
        if pen.miter_limit > 0.0:
            paint.setStrokeMiter(pen.miter_limit)
        if pen.dash is not None:
            intervals, phase = pen.dash
            ivals = [float(v) for v in intervals]
            if len(ivals) % 2 == 1:
                ivals = ivals + ivals
            if ivals and sum(ivals) > 0.0:
                effect = skia.DashPathEffect.Make(ivals, float(phase))
                if effect is not None:
                    paint.setPathEffect(effect)
        return paint

    def path(
        self,
        path: Path,
        pen: Pen | None = None,
        brush: Brush | None = None,
        *,
        even_odd: bool = False,
    ) -> None:
        """Stroke and/or fill ``path``.

        aggdraw's call convention is ``draw.path(path, pen, brush)`` —
        ``pen`` may be ``None`` for fill-only, ``brush`` may be ``None``
        for stroke-only.  Fill is rendered first so the stroke sits on
        top (matches aggdraw and standard PDF semantics).

        The optional keyword ``even_odd`` (wave 1330B — no aggdraw
        equivalent) switches the *fill* rule to even-odd.  This is a
        per-call setting so the same :class:`Path` instance can be
        reused for both rules across successive draws without leaking
        state.
        """
        sk_path = path._sk
        if even_odd:
            sk_path.setFillType(skia.PathFillType.kEvenOdd)
        else:
            sk_path.setFillType(skia.PathFillType.kWinding)
        canvas = self._canvas
        if brush is not None:
            canvas.drawPath(sk_path, self._make_fill_paint(brush.color))
            self._dirty = True
        if pen is not None:
            canvas.drawPath(sk_path, self._make_stroke_paint_from_pen(pen))
            self._dirty = True

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
        canvas = self._canvas
        if brush is not None:
            canvas.drawPath(p, self._make_fill_paint(brush.color))
            self._dirty = True
        if pen is not None:
            canvas.drawPath(
                p, self._make_stroke_paint(pen.color, pen.width),
            )
            self._dirty = True

    def line(self, xy: tuple[float, float, float, float], pen: Pen) -> None:
        if pen is None:
            return
        self._canvas.drawLine(
            float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3]),
            self._make_stroke_paint(pen.color, pen.width),
        )
        self._dirty = True

    def rectangle(
        self,
        xy: tuple[float, float, float, float],
        pen: Pen | None = None,
        brush: Brush | None = None,
    ) -> None:
        rect = skia.Rect.MakeLTRB(
            float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3]),
        )
        canvas = self._canvas
        if brush is not None:
            canvas.drawRect(rect, self._make_fill_paint(brush.color))
            self._dirty = True
        if pen is not None:
            canvas.drawRect(
                rect, self._make_stroke_paint(pen.color, pen.width),
            )
            self._dirty = True

    def ellipse(
        self,
        xy: tuple[float, float, float, float],
        pen: Pen | None = None,
        brush: Brush | None = None,
    ) -> None:
        rect = skia.Rect.MakeLTRB(
            float(xy[0]), float(xy[1]), float(xy[2]), float(xy[3]),
        )
        canvas = self._canvas
        if brush is not None:
            canvas.drawOval(rect, self._make_fill_paint(brush.color))
            self._dirty = True
        if pen is not None:
            canvas.drawOval(
                rect, self._make_stroke_paint(pen.color, pen.width),
            )
            self._dirty = True

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
        """Commit pending draws and blit pixels back to the PIL image.

        Fast path (wave 1330B): if no draw operations happened since the
        last flush — common when the renderer rebinds ``Draw`` purely to
        refresh after an external ``image.paste`` — this is a no-op.
        """
        if not self._dirty:
            return
        # Force any pending GPU/CPU work to materialise in the backing
        # buffer.  For raster surfaces this is essentially a no-op but
        # we call it for parity with future GPU-backed surfaces.
        self._surface.flushAndSubmit()
        # ``_pixels`` was handed to skia via MakeRasterDirect, so it
        # already holds the rendered RGBA bytes.
        rgba_bytes = bytes(self._pixels)
        rendered = _PILImage.frombytes("RGBA", self._size, rgba_bytes)
        # Convert back to the PIL image's original mode and paste in
        # place so callers that still hold a reference see the update.
        if self._pil.mode == "RGBA":
            self._pil.paste(rendered)
        elif self._pil.mode == "RGB":
            self._pil.paste(rendered.convert("RGB"))
        else:
            self._pil.paste(rendered.convert(self._pil.mode))
        self._dirty = False


__all__ = ["Brush", "Draw", "Path", "Pen"]
